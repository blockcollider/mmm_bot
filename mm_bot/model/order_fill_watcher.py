import time
import logging

import aiopubsub

from mm_bot.config import config
from mm_bot.model.constants import Status
from mm_bot.model.order import Order
from mm_bot.model.repository import OrderRepository
from mm_bot.exchange.taker.binance import Binance

# FIXME, rename the class
class OrderFillWatcher():

    def __init__(self, repository: OrderRepository, exchange, borderless_exchange): # TODO: PING add both exchange
        self._logger = logging.getLogger(f'{self.__class__.__name__}({exchange})')
        self._loop = aiopubsub.loop.Loop(self._run, delay = 2) # TODO move to config or use config.sleep

        self.exchange = exchange
        self.borderless_exchange = borderless_exchange
        self._repository = repository

        self._last_attempt_to_unlock = time.time()

    def start(self) -> None:
        self._logger.debug(f'Start to watch order fill events in {self.exchange}')
        self._loop.start()

    async def stop(self) -> None:
        self._logger.debug('Stopping')
        await self._loop.stop_wait()

    async def unlock_borderless_orders(self):
        # throttle it
        if time.time() - self._last_attempt_to_unlock < 10 * 60: # 10 min
            return

        self._last_attempt_to_unlock = time.time()
        unmatched_orders = await self.exchange.get_unmatched_orders()
        for unmatched_order in unmatched_orders:
            try:
                self._logger.info('Attempt unlocking tx: %s %s', unmatched_order['tx_hash'], unmatched_order['tx_output_index'])
                res = await self.exchange.unlock_tx(unmatched_order['tx_hash'], unmatched_order['tx_output_index'])
                self._logger.info('Done unlock with result: %s', res)
            except Exception as e:
                self._logger.exception('Error when unlocking')

    async def _run(self) -> None:
        self._logger.debug('Poking %s', self.exchange)

        if self.exchange.name == Binance.name:
            # since the orders in the db were created right after creating the orders from binance
            # we need to load it from the db
            open_orders = await self._repository.get_open_orders(self.exchange.side)
            self._logger.info('Open orders from db: %s', len(open_orders))
            order_statuses = await self.exchange.get_order_status(open_orders)
            for order, status, _ in order_statuses:
                if order.status == status:
                    continue

                self._logger.info('Updating order status: %s to %s', order.id, status)
                order.status = status
                await self._repository.update_order(order)


            filled_binance_orders = await self._repository.get_filled_orders(self.exchange.side)
            self._logger.info("Loaded filled binance orders: %s", len(filled_binance_orders))
            for order in filled_binance_orders:
                # load the maker order and init the transfer from binance
                status = order.status
                if status == Status.FILLED:
                    maker_order_id = order.maker_order_id
                    maker_order = await self._repository.get_order_by_id('maker', maker_order_id)
                    if maker_order is None:
                        continue

                    if maker_order.status == Status.EXPIRED:
                        self._logger.info("Maker order (id: %s) is in expired status", maker_order.id)
                        continue

                    is_in_settlement_window = await self.borderless_exchange.is_in_settlement_window(maker_order)
                    if not is_in_settlement_window:
                        self._logger.info("Order is not in the settle_window anymore so i will not send assets. Order id: %s", maker_order.id)
                        maker_order.status = Status.EXPIRED
                        self._logger.info("Mark order %s as %s", maker_order.id, maker_order.status)
                        await self._repository.update_order(maker_order)
                        continue

                    order_body = maker_order.order_body
                    taker_order_body = maker_order.taker_order_body

                    # init a transfer from binance, which is binance with asset as sends_from_chain
                    # to address is to_addr
                    sends_from_chain = order_body['sendsFromChain']
                    asset_id = sends_from_chain
                    to_addr = taker_order_body['receivesToAddress']
                    amount = order_body['sendsUnit']

                    await self.exchange.transfer_asset(asset_id, to_addr, amount)

                    maker_order.status = Status.SETTLED
                    self._logger.info("Mark order %s as %s", maker_order.id, maker_order.status)
                    await self._repository.update_order(maker_order)

        # borderless
        else:
            await self.unlock_borderless_orders()

            open_orders_from_exchange = await self.exchange.get_open_orders()
            open_order_exchange_hashs = set([o.tx_hash for o in open_orders_from_exchange])
            if len(open_orders_from_exchange) != 0:
                self._logger.info('Loaded open orders %s from exchange: %s', len(open_orders_from_exchange), open_orders_from_exchange)
                # save the open order to the db, as the borderless takes some time to mine the tx
                # the create_orders does not have order info immediately
                # find or create in db
                await self._repository.find_update_or_create_orders(open_orders_from_exchange)

            open_orders_from_db = await self._repository.get_open_orders(self.exchange.side)

            self._logger.info('Open orders %s to check status', len(open_orders_from_db))

            order_statuses = await self.exchange.get_order_status(open_orders_from_db)
            for order, status, taker_info in order_statuses:
                if order.status == status:
                    continue

                self._logger.info('Updating order status: %s to %s', order.id, status)
                order.status = status
                if taker_info is not None:
                    self._logger.info('Updating order taker_order_body: %s to %s', order.id, taker_info)
                    order.taker_order_body = taker_info

                await self._repository.update_order(order)

