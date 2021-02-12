from decimal import Decimal
from typing import DefaultDict, Dict, List, Optional, Tuple
import asyncio
import requests
import collections
import json
import logging
import os
import sys
from datetime import datetime

import math
import aiopubsub

import mm_bot.model.order
import mm_bot.model.book
import mm_bot.model.constants
import mm_bot.model.currency
from mm_bot.model.constants import OrderType
from mm_bot.exchange.base_exchange import BaseExchange
from mm_bot.config import config
from mm_bot.helpers import decimal_to_str
from mm_bot.model.currency import CurrencyPair

CLI_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'bin/main.js'))

from mm_bot.exchange.taker.binance import Binance
class JSCallFailedError(Exception):
    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr

async def _call_js_cli(args: List[str], logger: Optional[logging.Logger] = None):
    if logger:
        filtered_params = ('--bcPrivateKeyHex', '--privateKey')

        log_args = args.copy()
        for param in filtered_params:
            if param in log_args:
                log_args[log_args.index(param) + 1] = '***'

        logger.info('call_js_cli %s', ' '.join(log_args))

    dry_run = config('dry_run', parser=bool)
    cmd = ' '.join(['/usr/bin/env', 'node', str(CLI_PATH)] + args)
    proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
            )


    stdout, stderr = await proc.communicate()

    # print(f'[{cmd!r} exited with {proc.returncode}] out: {stdout}, err: {stderr}')

    if proc.returncode == 0:
        try:
            result = json.loads(stdout.decode('utf8'))
            if 'status' in result and result['status'] == 1:
                raise JSCallFailedError(result['status'], stdout.decode('utf8'))
            return result
        except:
            if logger:
                logger.exception('failed to decode results from borderless cli, %s', stdout.decode('utf8'))
            raise JSCallFailedError(1, stdout.decode('utf8'))
    else:
        err_msg = stderr.decode('utf8')
        if 'ECONNREFUSED' in err_msg:
            print('Exiting as it failed to connect to the miner', err_msg)
            sys.exit(1)
        raise JSCallFailedError(proc.returncode, err_msg)


CONFIRMATION_BLOCKS = {
    'btc': '1',
    'eth': '1',
    'neo': '1',
    'wav': '1',
    'lsk': '1',
    'dai': '1',
}

class Borderless(BaseExchange):

    def __init__(self, hub: aiopubsub.Hub, currency: mm_bot.model.currency.CurrencyPair,
            bc_address: str, bc_scookie: str, bc_wallet_address: str, bc_private_key_hex: str,
            base_address: str, counter_address: str):
        self.side = 'maker'
        self.name = 'borderless'
        self._logger = logging.getLogger(self.__class__.__name__)
        self._loop = aiopubsub.loop.Loop(self._run, delay = config('exchange_borderless_loop_delay', parser=int))
        self._hub = hub
        self._publisher = aiopubsub.Publisher(self._hub, self.name)
        self._currency = currency

        self._bc_rpc_address = bc_address
        self._bc_rpc_scookie = bc_scookie
        self._bc_wallet_address = bc_wallet_address
        self._bc_private_key_hex = bc_private_key_hex
        self._bc_base_address = base_address
        self._bc_counter_address = counter_address

        self._last_ask_best: mm_bot.model.book.PriceLevel = None
        self._last_bid_best: mm_bot.model.book.PriceLevel = None


    def get_confirmation_blocks(self, asset_id: str):
        asset_id = asset_id.lower()
        return CONFIRMATION_BLOCKS.get(asset_id, '1')

    def start(self) -> None:
        self._logger.debug('borderless start called')
        self._loop.start()


    async def get_account_balance(self):
        json = await _call_js_cli([
            'get', 'balance',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address
            ])

        result = {}
        for wallet_part, amount in json.items():
            result[wallet_part] = Decimal(amount)

        return result


    def calc_price(self, currency, order):
        """
        The price of ETH/BTC is 1 ETH worths how many BTC as BTC is quote
        if BUY ETH/BTC, you receive ETH and send BTC
            sendsUnit / receivesUnit
        if SELL ETH/BTC, you receive BTC and send ETH
            receivesUnit / sendsUnit

        Return decimal.Decimal
        """
        sends_unit = Decimal(order['sendsUnit'])
        receives_unit = Decimal(order['receivesUnit'])
        if self.is_buy_order(currency, order): # sends BTC and receives ETH
            return sends_unit / receives_unit
        else: # sell
            return receives_unit / sends_unit

    def calc_quantity(self, currency, order):
        if self.is_buy_order(currency, order): # sends BTC and receives ETH
            return Decimal(order['receivesUnit'])
        else: # sell, sends ETH
            return Decimal(order['sendsUnit'])

    def calc_fee(self, total_asset) -> Decimal:
        """
        The maker fee is very small
        """
        return Decimal('0')

    def is_buy_order(self, currency, order):
        """
        currency.base = receives_to_chain = bids and vice-versa
        eg: ETH/BTC, base is ETH, quote is BTC

        if BUY ETH/BTC, you receive ETH and send BTC
        if SELL ETH/BTC, you receive BTC and send ETH
        """
        base = currency.base.lower()
        counter = currency.counter.lower()

        return order['receivesToChain'].lower() == base and order['sendsFromChain'].lower() == counter


    def is_sell_order(self, currency: mm_bot.model.currency.CurrencyPair, order) -> bool:
        """
        currency.base = sends_from_chain = asks and vice-versa
        eg: ETH/BTC, base is ETH, quote is BTC

        if BUY ETH/BTC, you receive ETH and send BTC
        if SELL ETH/BTC, you receive BTC and send ETH
        """
        base = currency.base.lower()
        counter = currency.counter.lower()

        return order['sendsFromChain'].lower() == base and order['receivesToChain'].lower() == counter


    async def get_order_book(self, currency: mm_bot.model.currency.CurrencyPair) -> mm_bot.model.book.OrderBook:
        dry_run = config('dry_run', parser=bool)
        if dry_run:
            self._logger.info('DRY-RUN, get_order_book')
            return mm_bot.model.book.OrderBook([], [], 0, 0)

        json = await _call_js_cli([
            'get', 'order_book',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address,
            ])

        # key is price, value is quantity
        json_bids: DefaultDict[Decimal, Decimal] = collections.defaultdict(lambda: Decimal('0'))
        json_asks: DefaultDict[Decimal, Decimal] = collections.defaultdict(lambda: Decimal('0'))

        bid_nrg_rate = Decimal('0')
        ask_nrg_rate = Decimal('0')
        for order in json:
            price = self.calc_price(currency, order)
            quantity = self.calc_quantity(currency, order)

            if self.is_buy_order(currency, order):
                json_bids[price] += quantity
                sends_unit = Decimal(order['sendsUnit'])
                bid_nrg_rate += (Decimal(order['collateralizedNrg']) / sends_unit)
            elif self.is_sell_order(currency, order):
                json_asks[price] += quantity

                sends_unit = Decimal(order['sendsUnit'])
                ask_nrg_rate += (Decimal(order['collateralizedNrg']) / sends_unit)
            else:
                # idon't care this
                continue

        bid = [mm_bot.model.book.PriceLevel(price, quantity) for price, quantity in json_bids.items()]
        ask = [mm_bot.model.book.PriceLevel(price, quantity) for price, quantity in json_asks.items()]
        bid = sorted(bid, key=lambda p: p.price, reverse=True)
        ask = sorted(ask, key=lambda p: p.price)

        if len(bid) == 0:
            bid_nrg_rate = Decimal('0')
        else:
            bid_nrg_rate = bid_nrg_rate / len(bid)

        if len(ask) == 0:
            ask_nrg_rate = Decimal('0')
        else:
            ask_nrg_rate = ask_nrg_rate / len(ask)

        return mm_bot.model.book.OrderBook(bid, ask, bid_nrg_rate, ask_nrg_rate)

    async def get_price(self, asset_id) -> Decimal:
        asset = f'{asset_id}USDT'.upper()
        url = f'https://api.binance.com/api/v3/ticker/price?symbol={asset}'
        response = requests.get(url)

        assert response.status_code == 200
        data = response.json()

        return Decimal(data['price'])

    async def get_usdt_nrg_price(self) -> Decimal:
        currency = CurrencyPair('usdt', 'nrg')
        json = await _call_js_cli([
            'get', 'latest_usdt_nrg_price',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie
        ])
        self._logger.info(f'usdt/nrg {json}')

        return Decimal(json['price'])


    async def calculate_collateralized_nrg(self, asset_id, sends_unit):
        asset_id_usdt = await self.get_price(asset_id)
        usdt_nrg = await self.get_usdt_nrg_price()

        return str(math.ceil(Decimal(sends_unit) * asset_id_usdt * usdt_nrg))

    async def create_orders(self, orders_to_open):
        """
        orders_to_open:
        [{
            'qty': qty,
            'order_type': 'sell|buy',
            'price': best_bid_price_from_maker,
            'ask_nrg_rate': Decimal, # 1 ETH can buy ? NRG
            'bid_nrg_rate': Decimal # 1 BTC can buy ? NRG
        }]

        1. call js lib to create order in borderless
        2. create maker orders and save them to db

        """
        results = []
        for order in orders_to_open:
            if order['order_type'] == OrderType.BUY:
                # eg: ETH/BTC, base is ETH, quote is BTC

                # if BUY ETH/BTC, you receive ETH (base) and send BTC (counter)
                # currency.base = receives_to_chain = bids and vice-versa
                receives_to_chain = self._currency.base.lower()
                receives_unit = decimal_to_str(order['qty'])

                sends_from_chain = self._currency.counter.lower()
                sends_unit = decimal_to_str(order['qty'] * order['price'])

                # BTC NRG rate, if i default to send sends_unit (BTC)
                sends_from_address = self._bc_counter_address
                receives_to_address = self._bc_base_address
            else:
                # if SELL ETH/BTC, you receive BTC and send ETH
                receives_to_chain = self._currency.counter.lower()
                receives_unit = decimal_to_str(order['qty'] * order['price'])

                sends_from_chain = self._currency.base.lower()
                sends_unit = decimal_to_str(order['qty'])

                # ETH NRG rate, if i default to send sends_unit (ETH)

                sends_from_address = self._bc_base_address
                receives_to_address = self._bc_counter_address

            # I loss my collateralized_nrg, so use sends_from_chain
            collateralized_nrg = await self.calculate_collateralized_nrg(sends_from_chain, Decimal(sends_unit))

            order_body = {
                    'collateralizedNrg': collateralized_nrg,
                    'sendsFromChain': sends_from_chain,
                    'sendsUnit': sends_unit,
                    'receivesUnit': receives_unit,
                    'receivesToChain': receives_to_chain,
                    'orderType': order['order_type'],
                    'askNrgRate': decimal_to_str(order['ask_nrg_rate']),
                    'bidNrgRate': decimal_to_str(order['bid_nrg_rate']),
                    'qty': decimal_to_str(order['qty']),
            }
            self._logger.info(f'Creating order {order_body}')

            dry_run = config('dry_run', parser=bool)
            if dry_run:
                self._logger.info('DRY-RUN, create maker order, %s', order)
                continue
            else:
                json = await _call_js_cli([
                    'create', 'maker',
                    '--bcRpcAddress', self._bc_rpc_address,
                    '--bcRpcScookie', self._bc_rpc_scookie,
                    '--bcAddress', self._bc_wallet_address,
                    '--shiftMaker', self.get_confirmation_blocks(sends_from_chain),
                    '--shiftTaker', self.get_confirmation_blocks(receives_to_chain),
                    '--depositLength', config('exchange_borderless_deposit_length', parser=str),
                    '--settleLength', config('exchange_borderless_settlement_window_length', parser=str),
                    '--sendsFromChain', sends_from_chain,
                    '--receivesToChain', receives_to_chain,
                    '--sendsFromAddress', sends_from_address,
                    '--receivesToAddress', receives_to_address,
                    '--sendsUnit', sends_unit,
                    '--receivesUnit', receives_unit,
                    '--bcPrivateKeyHex', self._bc_private_key_hex,
                    '--collateralizedNrg', collateralized_nrg,
                    '--nrgUnit', collateralized_nrg, # does not allow partial order
                    '--additionalTxFee', '0'
                    ], self._logger)
                self._logger.info(f'Created order {json}')
                json['order_body'] = order_body

                results.append(json)

        return results


    async def get_unmatched_orders(self):
        dry_run = config('dry_run', parser=bool)
        if dry_run:
            self._logger.info('DRY-RUN, get_unmatched_orders')
            return []

        json = await _call_js_cli([
            'get', 'unmatched_orders',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address
            ], self._logger)

        unmatched_orders = []
        for order in json:
            tx_hash = order['txHash']
            tx_output_index = order['txOutputIndex']
            unmatched_orders.append({'tx_hash': tx_hash, 'tx_output_index': tx_output_index})

        return unmatched_orders

    async def unlock_tx(self, tx_hash, tx_output_index):
        json = await _call_js_cli([
            'create', 'unlock',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address,
            '--bcPrivateKeyHex', self._bc_private_key_hex,
            '--txHash', tx_hash,
            '--txOutputIndex', str(tx_output_index)
            ], self._logger)

        self._logger.info(f'unlocked tx: {tx_hash} {tx_output_index} with result: {json}')
        return json

    async def get_open_orders(self) -> List[mm_bot.model.order.Order]:
        dry_run = config('dry_run', parser=bool)
        if dry_run:
            self._logger.info('DRY-RUN, get_open_orders')
            return []

        json = await _call_js_cli([
            'get', 'open_orders',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address
            ], self._logger)

        orders = []
        utc_now = datetime.utcnow()
        for order in json:
            if self.is_buy_order(self._currency, order):
                order_type = OrderType.BUY
            elif self.is_sell_order(self._currency, order):
                order_type = OrderType.SELL
            else:
                # other orders that i don't care
                continue

            tx_hash = order['txHash']
            tx_output_index = order['txOutputIndex']
            block_height = str(order['tradeHeight'])

            o = mm_bot.model.order.MakerOrder(
                exchange=self.name,
                currency=self._currency.to_currency(),
                status=mm_bot.model.constants.Status.OPEN,
                order_type=order_type,
                order_body=order,
                tx_hash=tx_hash,
                tx_output_index=tx_output_index,
                block_height=block_height,
                taker_order_body={},
                created_at=utc_now,
                updated_at=utc_now
            )

            orders.append(o)

        return orders


    async def get_order_status(self, open_orders: List[mm_bot.model.order.Order]) -> List[Tuple[mm_bot.model.order.Order, mm_bot.model.constants.Status, Optional[Dict[str, str]]]]:
        if len(open_orders) > 10:
            self._logger.warn(f'More than 10 orders supplied ({len(open_orders)})')

        json = await _call_js_cli([
            'get', 'matched_orders',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--bcAddress', self._bc_wallet_address,
            ], self._logger)

        self._logger.info(f'Matched orders {len(json)}')

        matched_order_mapping = {}
        for matched_order in json:
            maker_order = matched_order['maker']
            tx_hash = maker_order['txHash']
            tx_output_index = maker_order['txOutputIndex']
            matched_order_mapping[tx_hash + '-' + str(tx_output_index)] = matched_order['taker']

        results = []
        for order in open_orders:
            key = order.tx_hash + '-' + str(order.tx_output_index)

            status = mm_bot.model.constants.Status.OPEN
            taker_info = None
            if key in matched_order_mapping:
                status = mm_bot.model.constants.Status.FILLED
                taker_info = matched_order_mapping[key]

            results.append((order, status, taker_info))

        return results

    async def is_in_settlement_window(self, maker_order: mm_bot.model.order.MakerOrder) -> bool:
        json = await _call_js_cli([
            'get', 'latest_block',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            ])
        latest_bc_block = Decimal(json['height'])

        block_height = Decimal(maker_order.block_height)
        settle_window = Decimal(maker_order.order_body['settlement'])

        self._logger.info(f'Check settlement window: latest block: {latest_bc_block}, tx block: {block_height}, settle_window: {settle_window}')
        return latest_bc_block <= block_height + settle_window

    async def transfer_asset(self, asset_id: str, to_addr: str, amount: Decimal, private_key: str, from_addr: str):
        self._logger.info(f'Transfer asset: {asset_id}, from: {from_addr}, to: {to_addr}, amount: {amount}')
        json = await _call_js_cli([
            'transfer', 'asset',
            '--bcRpcAddress', self._bc_rpc_address,
            '--bcRpcScookie', self._bc_rpc_scookie,
            '--assetId', asset_id,
            '--privateKey', private_key,
            '--from', from_addr,
            '--to', to_addr,
            '--amount', amount,
            ], self._logger)

        self._logger.info(f'Transfer result: {json}')

    async def _run(self) -> None:
        new_ob = await self.get_order_book(self._currency)
        if self._should_publish_change(new_ob):
            self._publisher.publish(('exchange', 'new_best'), new_ob)
            self._logger.debug('Order book\'s best changes, publishing %s', new_ob)


    def _should_publish_change(self, new_order_book: mm_bot.model.book.OrderBook) -> bool:
        """
        always publish to update the collateralizedNrg in the order book
        """
        return True


    async def cancel_orders(self, orders):
        for maker_order in orders:
            try:
                json = await _call_js_cli([
                    'cancel', 'maker',
                    '--bcRpcAddress', self._bc_rpc_address,
                    '--bcRpcScookie', self._bc_rpc_scookie,
                    '--makerOrderNrgUnit', str(maker_order.order_body['nrgUnit']),
                    '--makerOrderBase',  str(maker_order.order_body['base']),
                    '--makerOrderFixedUnitFee', str(maker_order.order_body['fixedUnitFee']),
                    '--makerOrderDoubleHashedBcAddress', maker_order.order_body['doubleHashedBcAddress'],
                    '--makerOrderCollateralizedNrg', maker_order.order_body['collateralizedNrg'],
                    '--makerOrderHash', maker_order.tx_hash,
                    '--makerOrderTxOutputIndex', str(maker_order.tx_output_index),
                    '--sendsFromAddress', maker_order.order_body['receivesToAddress'],
                    '--receivesToAddress', maker_order.order_body['sendsFromAddress'],
                    '--bcAddress', self._bc_wallet_address,
                    '--bcPrivateKeyHex', self._bc_private_key_hex,
                    '--collateralizedNrg', maker_order.order_body['collateralizedNrg'],
                    '--additionalTxFee', '0'
                    ], self._logger)

                self._logger.info('Canceled order: %s, with result: %s', maker_order, json)
            except:
                self._logger.exception('Failed to cancel order: %s', maker_order)

