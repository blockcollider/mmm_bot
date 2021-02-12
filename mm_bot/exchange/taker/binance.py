from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import logging
import time

import aiopubsub
import binance
from datetime import datetime

from mm_bot.exchange.base_exchange import BaseExchange
from mm_bot.config import config
import mm_bot.model.book
import mm_bot.model.constants
import mm_bot.model.currency
import mm_bot.model.order
from mm_bot.helpers import decimal_to_str
from binance.exceptions import BinanceAPIException, BinanceWithdrawException

def _binance_line_to_pricelevel (str_price_level: Tuple[str, str]) -> mm_bot.model.book.PriceLevel:
    price, quantity = str_price_level
    return mm_bot.model.book.PriceLevel(Decimal(price), Decimal(quantity))

class Binance(BaseExchange):
    name = 'binance'

    def __init__(self, hub: aiopubsub.Hub, currency: mm_bot.model.currency.CurrencyPair,
            loop_delay, api_key: str, api_secret: str):
        self.side = 'taker'
        self._logger = logging.getLogger(self.__class__.__name__)
        self._client = binance.AsyncClient(api_key, api_secret)
        self._loop = aiopubsub.loop.Loop(self._run, delay = loop_delay)
        self._hub = hub
        self._publisher = aiopubsub.Publisher(self._hub, self.name)
        self._currency = currency
        self._last_ask_best: mm_bot.model.book.PriceLevel = None
        self._last_bid_best: mm_bot.model.book.PriceLevel = None

        # https://www.binance.com/en/trade-rule
        self.min_total_order_value = {
            'BTC': Decimal('0.02'),
            'ETH': Decimal('0.2'),
            'USDT': Decimal('60'),
        }
        # https://www.binance.com/en/trade-rule
        self.min_price_movement = {
            'BTC': '0.000001',
            'WAVESBTC': '0.0000001',
            'ETH': '0.000001',
            'USDT': '0.01',
            'NEOUSDT': '0.001',
            'WAVESUSDT': '0.0001',
        }

    def normalize_price(self, price):
        price = price.normalize()

        currency = self._currency.to_currency(self.name)
        if currency in self.min_price_movement:
            min_price_movement = self.min_price_movement[currency]
        else:
            min_price_movement = self.min_price_movement[self._currency.counter]

        precision = len(min_price_movement.split('.')[-1])

        return decimal_to_str(price, precision)

    def start(self) -> None:
        self._logger.debug('binance start called')
        self._loop.start()

    def calc_fee(self, total_asset: Decimal) -> Decimal:
        fee_perc = Decimal('0.001')
        return fee_perc * total_asset

    async def stop(self) -> None:
        self._logger.info('binance stopping')
        await self._client.session.close()

    async def create_orders(self, orders_to_open):
        """
        orders_to_open:
        [{
            'profit': profit
            'qty': qty,
            'price': best_bid_price_from_maker
        }]
        """
        dry_run = config('dry_run', parser=bool)
        orders_to_return = []
        for order in orders_to_open:
            if order['order_type'] == mm_bot.model.constants.OrderType.SELL:
                order_side = binance.AsyncClient.SIDE_SELL
            else:
                order_side = binance.AsyncClient.SIDE_BUY

            if dry_run:
                self._logger.info(f'DRY-RUN: Would create order {order}')
            else:
                price = self.normalize_price(order['price'])
                res = await self._client.create_order(
                        symbol=self._currency.to_currency(self.name),
                        side=order_side,
                        type=binance.AsyncClient.ORDER_TYPE_LIMIT,
                        timeInForce=binance.AsyncClient.TIME_IN_FORCE_GTC,
                        quantity=order['qty'],
                        price=price,
                        )

                order_str = dict(order)
                order_str['order_id'] = res['orderId']
                order_str['price'] = price
                order_str['qty'] = str(order['qty'])

                orders_to_return.append(order_str)

                self._logger.info(f'Created order {order_str} with res: {res}')

        return orders_to_return


    async def get_open_orders(self) -> List[mm_bot.model.order.Order]:
        """
        see https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#current-open-orders-user_data

        TODO should try to fetch existing orders from persistence and only include new - in that case
        return value should be something like ([existing], [unknown])
        """
        symbol = f'{self._currency.base}{self._currency.counter}'
        self._logger.debug(f'Getting open orders: symbol {symbol}')
        res = await self._client.get_open_orders(symbol = symbol, recvWindow = 60000, timestamp = int(time.time()))
        orders = []
        utc_now = datetime.utcnow()
        for order in res:
            o = mm_bot.model.order.TakerOrder(
                exchange= self.name,
                status=order['status'],
                order_type=order['type'],
                currency=self._currency.to_currency('bot'),
                order_body=order,
                order_id=order['orderId'],
                maker_order_id=-1, # set a dummy value
                created_at=utc_now,
                updated_at=utc_now,
            )
            orders.append(o)

        return orders

    async def transfer_asset(self, asset_id: str, to_addr: str, amount: Decimal, private_key: Optional[str]=None, from_addr: Optional[str]=None):
        asset_id = asset_id.upper()
        if asset_id == 'WAV':
            asset_id = 'WAVES'

        self._logger.info('Init transfer in Binance for asset: %s, to_addr: %s, amount: %s', asset_id, to_addr, amount)

        try:
            result = await client.withdraw(
                    asset=asset_id,
                    address=to_addr,
                    amount=amount)

            self._logger.info('Succeeded, withdraw  for asset: %s, to_addr: %s, amount: %s', asset_id, to_addr, amount)
        except BinanceAPIException as e:
            self._logger.info('Error while calling binance: %s', str(e))
            raise e
        except BinanceWithdrawException as e:
            self._logger.info('Error while withdraw: %s', str(e))
            raise e
        except:
            self._logger.info('Failed to withdraw from Binance, it is likely that your api key does not have withdraw restriction enabled or the ip does not match your whitelisted ips')
            raise RuntimeError('Failed to withdraw from Binance')

    async def get_order_status(self, orders: List[mm_bot.model.order.TakerOrder]) -> List[Tuple[mm_bot.model.order.Order, mm_bot.model.constants.Status, Optional[Dict[str, str]]]]:
        """
        see https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#public-api-endpoints (order status)
        and
        https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#query-order-user_data
        """
        symbol = f'{self._currency.base}{self._currency.counter}'
        results = []
        for order in orders:
            self._logger.debug(f'Getting status for order ID: {order.order_id}, symbol {symbol}')
            res = await self._client.get_order(symbol = symbol, orderId = order.order_id)

            status_mapping = {
                self._client.ORDER_STATUS_NEW: mm_bot.model.constants.Status.OPEN,
                self._client.ORDER_STATUS_PARTIALLY_FILLED: mm_bot.model.constants.Status.FILLED,
                self._client.ORDER_STATUS_FILLED: mm_bot.model.constants.Status.FILLED,
                self._client.ORDER_STATUS_CANCELED: mm_bot.model.constants.Status.CANCELED,
                self._client.ORDER_STATUS_PENDING_CANCEL: mm_bot.model.constants.Status.CANCELED,
                self._client.ORDER_STATUS_REJECTED: mm_bot.model.constants.Status.CANCELED,
                self._client.ORDER_STATUS_EXPIRED: mm_bot.model.constants.Status.CANCELED,
            }

            status = status_mapping[res['status']]
            results.append((order, status, None))

        return results


    async def get_order_book(self, currency: mm_bot.model.currency.CurrencyPair) -> mm_bot.model.book.OrderBook:
        """
        see https://github.com/binance-exchange/binance-official-api-docs/blob/master/rest-api.md#order-book
        """
        self._logger.debug(f'Fetching orderbook for {currency}')
        data = await self._client.get_order_book(symbol = f'{currency.base}{currency.counter}')
        asks = [_binance_line_to_pricelevel(l) for l in data['asks']]
        bids = [_binance_line_to_pricelevel(l) for l in data['bids']]

        return mm_bot.model.book.OrderBook(asks, bids, 0, 0)


    async def _run(self) -> None:
        new_ob = await self.get_order_book(self._currency)
        if self._should_publish_change(new_ob):
            self._logger.debug('Order book\'s best changed, publishing, %s', new_ob)
            self._publisher.publish(('exchange', 'new_best'), new_ob)


    def _should_publish_change(self, new_order_book: mm_bot.model.book.OrderBook) -> bool:
        if self._last_bid_best is None or self._last_bid_best != new_order_book.bid[0]:
            self._last_bid_best = new_order_book.bid[0]
            self._last_ask_best = new_order_book.ask[0]
            return True

        if self._last_ask_best is None or self._last_ask_best != new_order_book.ask[0]:
            self._last_bid_best = new_order_book.bid[0]
            self._last_ask_best = new_order_book.ask[0]
            return True

        return False
