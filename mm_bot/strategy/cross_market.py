import os
import time
import signal
import logging
import math
from typing import List
from decimal import Decimal, ROUND_CEILING, ROUND_DOWN
import traceback


import json
import aiopubsub
from datetime import datetime

from mm_bot.model.order_fill_watcher import OrderFillWatcher
from mm_bot.model.constants import Status

from mm_bot.model.order import MakerOrder, TakerOrder
from mm_bot.model.constants import OrderType
from mm_bot.model.currency import CurrencyPair
from mm_bot.model.book import OrderBook
from mm_bot.model.repository import OrderRepository
from mm_bot.config import config


class CrossMarketStrategy:
    HEARTBEAT_DELAY = config('sleep', parser=int)

    def __init__(self, hub: aiopubsub.Hub, repository: OrderRepository, taker_exchange, maker_exchange, currency: CurrencyPair,
                 max_open_orders: int, min_profitability_rate: Decimal, max_qty_per_order: Decimal,
                 cancel_order_threshold: Decimal, should_cancel_order: bool):
        self._logger = logging.getLogger(f'{self.__class__.__name__}({taker_exchange}, {maker_exchange}, {currency})')
        self._hub = hub
        self._repository = repository
        self.taker_exchange = taker_exchange
        self.maker_exchange = maker_exchange
        self._currency_pair = currency
        self._max_open_orders = max_open_orders
        self._max_qty_per_order = max_qty_per_order
        self._cancel_order_threshold = cancel_order_threshold
        self._should_cancel_order = should_cancel_order
        self._min_profitability_rate = min_profitability_rate
        self._loop = aiopubsub.loop.Loop(self._run, delay=CrossMarketStrategy.HEARTBEAT_DELAY)
        self._subscriber = aiopubsub.Subscriber(self._hub, 'cross_market_strategy')
        self._order_fill_watchers: List[OrderFillWatcher] = []
        self._taker_order_book = None
        self._maker_order_book = None

    def start(self) -> None:
        self._logger.info('strategy start called')
        self._subscriber.subscribe(('*', 'exchange', 'new_best'))

        self.maker_exchange.start()
        self.taker_exchange.start()
        # TODO move fill watchers to exchanges

        taker_exchange_watcher = OrderFillWatcher(self._repository, self.taker_exchange, self.maker_exchange)
        taker_exchange_watcher.start()

        maker_exchange_watcher = OrderFillWatcher(self._repository, self.maker_exchange, self.maker_exchange)
        maker_exchange_watcher.start()

        self._order_fill_watchers.append(taker_exchange_watcher)
        self._order_fill_watchers.append(maker_exchange_watcher)

        self._loop.start()

    async def stop(self) -> None:
        self._logger.info('stopping')
        for watcher in self._order_fill_watchers:
            await watcher.stop()

        # maker doesn't need stopping
        self._logger.info('Stopping taker exchange')
        await self.taker_exchange.stop()
        await self._loop.stop_wait()

    async def _run(self) -> None:
        """
        Exchanges send us updates of bests
        When something is consumed regardless of from where
        we know that something has changes and we need to check
        all conditions and adjust orders accordingly
        """
        error = ''
        try:
            self._logger.debug('loop tick')
            key, value = await self._subscriber.consume()
            self._logger.debug(f'Consuming {key}')

            exchange, _, what = key
            self._logger.debug(f'{exchange} published {what}')

            if what == 'new_best':
                self._update_order_book(exchange, value)

            await self._recalculate_and_recreate_orders()
        except:
            error = traceback.format_exc()
            self._logger.info('Transient error in the run loop, it will continue next run', exc_info=True)
        finally:
            self._heartbeat(error)

    def _heartbeat(self, error):
        utc_now = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        epoch_time = int(time.time())
        s = f'{utc_now},{epoch_time},"{error}"'
        heartbeat_file = os.environ.get('HEARTBEAT_FILE', None)
        if heartbeat_file is None:
            return

        with open(heartbeat_file, 'w+') as f:
            f.write(s)

    def _update_order_book(self, exchange: str, value: OrderBook) -> None:
        if exchange == self.taker_exchange.name:
            self._logger.debug('Updating exchange %s with new OB', exchange)
            self._taker_order_book = value

        if exchange == self.maker_exchange.name:
            self._logger.debug('Updating exchange %s with new OB', exchange)
            self._maker_order_book = value

    async def _recalculate_and_recreate_orders(self):
        maker_exchange_balance = await self.maker_exchange.get_account_balance()

        if maker_exchange_balance['confirmed'] == Decimal('0'):
            self._logger.info('No NRG in borderless, will not create orders. balance data: %s', {key: str(val) for key, val in maker_exchange_balance.items()})
        else:
            await self.adjust_open_maker_orders()
            await self.create_open_maker_orders()
        await self.create_hedge_orders_in_taker()

    async def create_open_maker_orders(self):
        """
        Create open orders in maker exchange if it is profitable

        1. get order book from maker exchange
        2. get order book from taker exchange
        3. any chance to make profit with min_profitability_rate
            best_bid(maker) < best_bid(taker)
            best_ask(maker) > best_ask(taker)
        4. check existing open orders, as we don't want too much exposure
        """
        self._logger.debug('create_open_maker_orders()')
        max_open_orders = self._max_open_orders
        # Note: we shoud use exchange as the source of truth,
        # as the open order in the borderless can expire
        current_open_maker_orders = await self.maker_exchange.get_open_orders()
        current_open_maker_order_count = len(current_open_maker_orders)
        current_open_taker_orders = await self.taker_exchange.get_open_orders()
        current_open_taker_order_count = len(current_open_taker_orders)
        open_order_quota = max_open_orders - current_open_maker_order_count - current_open_taker_order_count

        self._logger.info('Maker side: %s, taker side: %s', current_open_maker_order_count, current_open_taker_order_count)

        if open_order_quota <= 0:
            self._logger.info('Skip. reach max_open_orders: %s, with maker side: %s, taker side: %s',
                              max_open_orders, current_open_maker_order_count, current_open_taker_order_count
                              )
            return

        if not self._taker_order_book or not self._maker_order_book:
            self._logger.debug(
                'strategy has to have orderbooks from both exchanges - not running create_open_maker_orders yet')
            return

        order_book_in_taker_exchange = self._taker_order_book
        order_book_in_maker_exchange = self._maker_order_book

        buy_to_open_result = self.calc_buy_to_open(
            order_book_in_taker_exchange, order_book_in_maker_exchange
        )
        sell_to_open_result = self.calc_sell_to_open(
            order_book_in_taker_exchange, order_book_in_maker_exchange
        )
        orders_to_open = buy_to_open_result + sell_to_open_result
        if len(orders_to_open) == 0:
            self._logger.info('Skip. no profitable orders')
            return

        # calc avg nrg rate
        ask_nrg_rate = order_book_in_maker_exchange.ask_nrg_rate
        bid_nrg_rate = order_book_in_maker_exchange.bid_nrg_rate
        for order in orders_to_open:
            order['ask_nrg_rate'] = ask_nrg_rate
            order['bid_nrg_rate'] = bid_nrg_rate

        orders_to_open = sorted(orders_to_open, key=lambda o: o['profit'], reverse=True)
        self._logger.info('Create. attempt to create maker orders: %s', orders_to_open)
        results = await self.maker_exchange.create_orders(orders_to_open)
        self._logger.info('Create. result: %s', results)

        created_maker_orders = []
        utc_now = datetime.utcnow()
        for result in results:
            if result['status'] != 0:
                continue

            tx_hash = result['txHash']
            order_body = result['order_body']
            o = MakerOrder(
                exchange=self.maker_exchange.name,
                status=Status.OPEN,
                order_type=order_body['orderType'],
                currency=self._currency_pair.to_currency('bot'),
                order_body=order_body,
                tx_hash=tx_hash,
                tx_output_index=0,
                block_height=None,
                taker_order_body={},
                created_at=utc_now,
                updated_at=utc_now,
            )
            created_maker_orders.append(o)

        self._logger.info('Persisted %s maker orders in the db', len(created_maker_orders))
        await self._repository.create_orders(created_maker_orders)

    async def create_hedge_orders_in_taker(self):
        """
        1. load all filled orders from maker_orders table
        2. load all open orders from taker_orders table
        3. create additional taker orders for the filled maker orders
        """
        self._logger.debug('create_hedge_orders_in_taker()')

        if not self._taker_order_book:
            self._logger.debug('not received taker OB yet - nothing to do in create_hedge_orders_in_taker')
        filled_maker_orders = await self._repository.get_filled_orders('maker')
        if len(filled_maker_orders) == 0:
            self._logger.info('create_hedge_orders_in_taker() check ended - no filled maker orders')
            return

        filled_maker_order_ids = set([o.id for o in filled_maker_orders])
        for order in await self._repository.get_taker_orders_by_maker_id(filled_maker_order_ids):
            filled_maker_order_ids.discard(order.maker_order_id)

        if len(filled_maker_order_ids) == 0:
            self._logger.info('No filled maker orders reported, nothing to do in create_hedge_orders_in_taker')
            return

        self._logger.info('Load filled maker orders: %s', filled_maker_order_ids)
        order_book_in_taker_exchange = self._taker_order_book
        orders_to_open = []
        for order in filled_maker_orders:
            if order.id in filled_maker_order_ids:
                orders_to_open.append(
                    self.construct_taker_order_request(order, order_book_in_taker_exchange)
                )

        self._logger.info('Create. attempt to create taker orders: %s', orders_to_open)
        orders_to_open_res = await self.taker_exchange.create_orders(orders_to_open)

        created_taker_orders = []
        utc_now = datetime.utcnow()
        for taker_order_req in orders_to_open_res:
            o = TakerOrder(
                exchange=self.taker_exchange.name,
                status=Status.OPEN,
                order_type=taker_order_req['order_type'],
                currency=self._currency_pair.to_currency('bot'),
                order_body=taker_order_req,
                order_id=taker_order_req['order_id'],
                maker_order_id=taker_order_req['maker_order_id'],
                created_at=utc_now,
                updated_at=utc_now,
            )
            created_taker_orders.append(o)

        await self._repository.create_orders(created_taker_orders)

    def construct_taker_order_request(self, maker_order, taker_order_book):
        """
        {'qty': '', 'price': ''}
        """
        qty = maker_order.quantity()
        maker_order_price = maker_order.price()
        maker_order_type = maker_order.order_type

        order_type = None
        if maker_order_type == OrderType.BUY:  #
            # sell in taker exchange
            min_sell_price = (1 + self._min_profitability_rate) * maker_order_price
            price = max(taker_order_book.bid[0].price, min_sell_price)
            order_type = OrderType.SELL
        else:
            max_buy_price = (1 - self._min_profitability_rate) * maker_order_price
            price = min(max_buy_price, taker_order_book.ask[0].price)
            order_type = OrderType.BUY

        return {
            'qty': qty,
            'price': price,
            'order_type': order_type,
            'maker_order_id': maker_order.id
        }

    def calc_buy_to_open(self, order_book_in_taker_exchange, order_book_in_maker_exchange):
        """
        Return [{}]
        """
        best_bid_price_from_taker = order_book_in_taker_exchange.bid[0].price
        if len(order_book_in_maker_exchange.bid) == 0:
            best_bid_price_from_maker = best_bid_price_from_taker / (Decimal('1') + 2 * self._min_profitability_rate)
            if '.' in str(best_bid_price_from_taker):
                prec = len(str(best_bid_price_from_taker).split('.')[-1])
            else:
                prec = 0

            n_pow = Decimal(math.pow(10, prec))
            best_bid_price_from_maker = (best_bid_price_from_maker * n_pow).to_integral_value(ROUND_CEILING) / n_pow
        else:
            best_bid_price_from_maker = order_book_in_maker_exchange.bid[0].price

        # check balance, BUY ETH/BTC
        # to simplify, get the best bid
        if best_bid_price_from_taker <= best_bid_price_from_maker:
            self._logger.info(
                'calc_buy_to_open() - skipping: best_bid_price_from_taker: %s is <= the best_bid_price_from_maker: %s',
                best_bid_price_from_taker, best_bid_price_from_maker
                )
            return []

        qty = min(order_book_in_taker_exchange.bid[0].quantity, self._max_qty_per_order)
        qty = max(qty, self.taker_exchange.min_total_order_value[self._currency_pair.counter.upper()])
        profit = (best_bid_price_from_taker - best_bid_price_from_maker) / best_bid_price_from_maker

        if profit < self._min_profitability_rate:
            self._logger.info('Skip. profit: %s is less than the min_profitability_rate: %s',
                              profit, self._min_profitability_rate
                              )
            return []

        return [{
            'profit': profit,
            'qty': qty,
            'order_type': OrderType.BUY,
            'price': best_bid_price_from_maker
        }]

    def calc_sell_to_open(self, order_book_in_taker_exchange, order_book_in_maker_exchange):
        """
        Return [{
            'profit': Decimal,
            'qty': Decimal,
            'order_type': 'buy|sell',
            'price': Decimal
        }]
        """
        best_ask_price_from_taker = order_book_in_taker_exchange.ask[0].price  # Decimal
        if len(order_book_in_maker_exchange.ask) == 0:
            best_ask_price_from_maker = best_ask_price_from_taker / (Decimal('1') - 2 * self._min_profitability_rate)
            if '.' in str(best_ask_price_from_taker):
                prec = len(str(best_ask_price_from_taker).split('.')[-1])
            else:
                prec = 0

            n_pow = Decimal(math.pow(10, prec))
            best_ask_price_from_maker = (best_ask_price_from_maker * n_pow).to_integral_value(ROUND_DOWN) / n_pow

        else:
            best_ask_price_from_maker = order_book_in_maker_exchange.ask[0].price  # Decimal

        # check balance, SELL ETH/BTC
        # to simplify, get the best ask
        if best_ask_price_from_taker >= best_ask_price_from_maker:
            self._logger.info(
                'calc_sell_to_open() - skipping: best_ask_price_from_taker: %s is >= than the best_ask_price_from_maker: %s',
                best_ask_price_from_taker, best_ask_price_from_maker
                )
            return []

        qty = min(order_book_in_taker_exchange.ask[0].quantity, self._max_qty_per_order)
        qty = max(qty, self.taker_exchange.min_total_order_value[self._currency_pair.counter.upper()])
        profit = (best_ask_price_from_maker - best_ask_price_from_taker) / best_ask_price_from_maker

        if profit < self._min_profitability_rate:
            self._logger.info('Skip. profit: %s is less than the min_profitability_rate: %s',
                              profit, self._min_profitability_rate
                              )
            return []

        return [{
            'profit': profit,
            'qty': qty,
            'order_type': OrderType.SELL,
            'price': best_ask_price_from_maker
        }]

    async def adjust_open_maker_orders(self):
        """
        The maker market is borderless, there is no way to update the price.
        The only way to "adjust" your order is to take that order yourself (via taker order) on the Interchange and then reposting your original maker order with your desired updates.
        But be aware that "adjusting" an order will it cost more fees to execute.
        """
        self._logger.debug('adjust_open_maker_orders()')
        if not self._taker_order_book:
            return

        if not self._should_cancel_order:
            self._logger.info('Dont cancle orders as should_cancel_order is False')
            return

        order_book_in_taker_exchange = self._taker_order_book

        orders_to_cancel = []
        open_orders = await self.maker_exchange.get_open_orders()
        for open_order in open_orders:
            potential_profit = self.calculate_profitability(open_order, order_book_in_taker_exchange)
            if potential_profit <= self._cancel_order_threshold:
                orders_to_cancel.append(open_order)

        if orders_to_cancel:
            for order in orders_to_cancel:
                self._logger.info('Canceling maker orders: %s', order)
            await self.maker_exchange.cancel_orders(orders_to_cancel)

    def calculate_profitability(self, open_order: MakerOrder, order_book_in_taker_exchange: OrderBook):
        '''
        check order_type of open_order, is buy to open or sell to open
        '''
        price = open_order.price()
        quantity = open_order.quantity()

        if open_order.is_buy():  # so sell in taker exchange, check bid price and qty in the order book
            bid_price = order_book_in_taker_exchange.bid[0].price

            cost_to_hedge = bid_price * quantity # sell in the taker exchange
            profit = cost_to_hedge - price * quantity
        elif open_order.is_sell():  # buy in taker exchange, check ask price
            ask_price = order_book_in_taker_exchange.ask[0].price

            cost_to_hedge = ask_price * quantity # buy in taker exchange
            profit = price * quantity - cost_to_hedge
        else:
            raise RuntimeError('Invalid order_type')

        profit_rate = (profit - self.taker_exchange.calc_fee(cost_to_hedge)) / price * quantity
        log_line = {
            'price': str(price),
            'quantity': str(quantity),
            'is_buy': open_order.is_buy(),
            'cost_to_hedge': str(cost_to_hedge),
            'profit_before_fee': str(profit),
            'profit_rate': str(profit_rate)
        }
        self._logger.info(json.dumps(log_line))

        return profit_rate
