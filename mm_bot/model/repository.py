from typing import List, Set, Union, Optional
from typing_extensions import Literal
import dataclasses

import arrow
import asyncio
from databases import Database
from sqlalchemy import func, select, bindparam, text

from mm_bot.model.constants import Status, OrderType
from mm_bot.model.order import Order, MakerOrder, MakerOrdersTable, TakerOrder, TakerOrdersTable
from mm_bot.helpers import decimal_to_str


class OrderRepository:

    def __init__(self, db_path: str):
        self._db = Database(db_path)
        self._connected = False


    # TODO this should be a decorator
    async def _ensure_connected(self):
        if not self._connected:
            await self._db.connect()
            self._connected = True


    async def close(self):
        if self._connected:
            await self._db.disconnect()

    async def get_all_orders(self, side: Union[Literal['maker'], Literal['taker']]) -> List[Order]:
        return await self._get_orders(side, None)

    async def get_open_orders(self, side: Union[Literal['maker'], Literal['taker']]) -> List[Order]:
        return await self._get_orders(side, Status.OPEN)


    async def get_filled_orders(self, side: Union[Literal['maker'], Literal['taker']]) -> List[Order]:
        return await self._get_orders(side, Status.FILLED)


    async def count_open_orders(self, side: Union[Literal['maker'], Literal['taker']]) -> int:
        return await self._get_orders(side, Status.OPEN, count = True)


    async def count_filled_orders(self, side: Union[Literal['maker'], Literal['taker']]) -> int:
        return await self._get_orders(side, Status.FILLED, count = True)


        filled_maker_order_ids = set([o.id for o in filled_maker_orders])
        for order in TakerOrder.select(lambda o: o.maker_order_id in filled_maker_order_ids):
            filled_maker_order_ids.discard(order.maker_order_id)

    async def get_order_by_id(self, side: Union[Literal['maker'], Literal['taker']], _id: int) -> Optional[Order]:
        if side == 'maker':
            tbl_cls = MakerOrdersTable
            record_cls = MakerOrder
        elif side == 'taker':
            tbl_cls = TakerOrdersTable
            record_cls = TakerOrder
        else:
            raise RuntimeError('invalid side')

        await self._ensure_connected()

        query = tbl_cls.select().where(tbl_cls.c.id == _id)
        row = await self._db.fetch_one(query=query)
        if row is None:
            return None

        row_id, *fields = row

        order = record_cls(*fields)
        order.id = row_id

        return order


    async def get_taker_orders_by_maker_id(self, maker_ids: Set[int]) -> List[TakerOrder]:
        await self._ensure_connected()
        query = TakerOrdersTable.select().where(TakerOrdersTable.c.maker_order_id.in_(maker_ids))
        res = await self._db.fetch_all(query=query)
        # TODO this mapping to record class should be pulled up to function outside of repo class
        results = []
        res = await self._db.fetch_all(query=query)
        for row_id, *fields in res:
            record = TakerOrder(*fields)
            record.id = row_id
            results.append(record)

        return results

    async def _get_orders(self, side: Union[Literal['maker'], Literal['taker']], status: Optional[Status], count=False) -> Union[List[Order], bool]:
        if side == 'maker':
            tbl_cls = MakerOrdersTable
            record_cls = MakerOrder
        elif side == 'taker':
            tbl_cls = TakerOrdersTable
            record_cls = TakerOrder
        else:
            raise RuntimeError('invalid side')

        await self._ensure_connected()

        if count:
            query = select([func.count()]).select_from(tbl_cls)
            if status:
                query = query.where(tbl_cls.c.status == status)
            count, = await self._db.fetch_one(query = query)
            return count
        else:
            query = tbl_cls.select()
            if status:
                query = query.where(tbl_cls.c.status == status)
            results = []
            res = await self._db.fetch_all(query=query)
            for row_id, *fields in res:
                record = record_cls(*fields)
                record.id = row_id
                results.append(record)

            return results

    async def find_update_or_create_orders(self, orders: List[Order]) -> List[Order]:
        if len(orders) == 0:
            return orders

        if isinstance(orders[0], MakerOrder):
            tbl_cls = MakerOrdersTable
            order_identifier_key = MakerOrder.IDENTIFIER
        elif isinstance(orders[0], TakerOrder):
            tbl_cls = TakerOrdersTable
            order_identifier_key = TakerOrder.IDENTIFIER
        else:
            raise RuntimeError('invalid side')

        identifiers = list(map(lambda o: getattr(o, order_identifier_key), orders))
        select_query = tbl_cls.select().where(getattr(tbl_cls.c, order_identifier_key).in_(identifiers))
        existing_orders = await self._db.fetch_all(query=select_query)

        existing_order_identifiers = set(map(lambda o: getattr(o, order_identifier_key), existing_orders))
        existing_order_identifier_to_order_mapping = dict(
            map(lambda o: (getattr(o, order_identifier_key), o), existing_orders)
        )

        new_orders = list(filter(lambda o: getattr(o, order_identifier_key) not in existing_order_identifiers, orders))
        newly_created_orders = await self.create_orders(new_orders)

        orders_to_be_updated = []
        for order in orders:
            identifier = getattr(order, order_identifier_key)
            if identifier in existing_order_identifiers:
                order.id = existing_order_identifier_to_order_mapping[identifier].id
                orders_to_be_updated.append(order)

        await self.update_orders(orders_to_be_updated)

        return orders_to_be_updated + newly_created_orders

    async def create_orders(self, orders: List[Order]) -> List[Order]:
        """
        self._db.execute_many(query=query, values=values) does not return ids

        since the number of orders is small, we can just invoke create_order one by one instead of
        using execute_many
        """
        tasks = map(lambda order: self.create_order(order), orders)
        return await asyncio.gather(*tasks)

    async def create_order(self, order: Order) -> Order:
        """{
            'profit': profit,
            'qty': qty,
            'order_type': OrderType.BUY,
            'price': best_bid_price_from_maker
        }
        """

        if isinstance(order, MakerOrder):
            tbl_cls = MakerOrdersTable
        elif isinstance(order, TakerOrder):
            tbl_cls = TakerOrdersTable
        else:
            raise RuntimeError('invalid side')

        await self._ensure_connected()
        query = tbl_cls.insert()
        value = dataclasses.asdict(order)
        row_id = await self._db.execute(query=query, values=value)
        order.id = row_id

        return order

    async def update_order(self, order: Order) -> Order:
        """
        order has to have id in it
        """
        if not order.id:
            raise RuntimeError('Cannot UPDATE non-persisted order')

        if isinstance(order, MakerOrder):
            tbl_cls = MakerOrdersTable
        elif isinstance(order, TakerOrder):
            tbl_cls = TakerOrdersTable
        else:
            raise RuntimeError('invalid side')

        await self._ensure_connected()
        values = dataclasses.asdict(order)
        del values['id']
        query = tbl_cls.update().where(tbl_cls.c.id == order.id).values(values)
        await self._db.execute(query = query)

    async def update_orders(self, orders: List[Order]) -> List[Order]:
        tasks = list(map(lambda order: self.update_order(order), orders))
        await asyncio.gather(*tasks)

    async def delete_order(self, order: Order) -> None:
        if isinstance(order, MakerOrder):
            tbl_cls = MakerOrdersTable
        elif isinstance(order, TakerOrder):
            tbl_cls = TakerOrdersTable
        else:
            raise RuntimeError('invalid side')

        if not order.id:
            raise RuntimeError('Cannot DELETE non-persisted order')

        query = tbl_cls.delete().where(tbl_cls.c.id == order.id)
        await self._db.execute(query = query)

    async def update_status(self, orders: List[Order], new_status: str) -> None:
        if len(orders) == 0:
            return

        order_ids = map(lambda d: d.id, orders)

        if isinstance(orders[0], MakerOrder):
            tbl_cls = MakerOrdersTable
        elif isinstance(orders[0], TakerOrder):
            tbl_cls = TakerOrdersTable
        else:
            raise RuntimeError('invalid side')

        stmt = tbl_cls.update().where(tbl_cls.c.id.in_(order_ids)).values({'status': new_status})
        await self._db.execute(query=stmt)

# for api #

    async def get_filled_orders_in_range(self, start_date, end_date):
        query = TakerOrdersTable.select().where(
            TakerOrdersTable.c.status == Status.FILLED
        )
        filled_taker_orders = []
        res = await self._db.fetch_all(query=query)
        for row_id, *fields in res:
            record = TakerOrder(*fields)
            record.id = row_id
            filled_taker_orders.append(record)
        if len(filled_taker_orders) == 0:
            return []

        maker_order_ids = list(map(lambda o: o.maker_order_id, filled_taker_orders))
        query_maker = MakerOrdersTable.select().where(MakerOrdersTable.c.id.in_(maker_order_ids))
        filled_maker_orders_res = await self._db.fetch_all(query=query_maker)
        id_to_maker_order_map = {}
        for row_id, *fields in filled_maker_orders_res:
            record = MakerOrder(*fields)
            record.id = row_id
            id_to_maker_order_map[str(row_id)] = record

        maker_taker_pairs = []
        for taker_order in filled_taker_orders:
            maker_order_id = str(taker_order.maker_order_id)
            maker_order = id_to_maker_order_map[maker_order_id]

            if maker_order.order_type == OrderType.BUY:
                profit = - maker_order.price() * maker_order.quantity() + taker_order.price() * taker_order.quantity()
            else:
                profit = maker_order.price() * maker_order.quantity() - taker_order.price() * taker_order.quantity()

            profit = decimal_to_str(profit)
            maker_taker_pairs.append({
                'currency': taker_order.currency,
                'created_at': taker_order.created_at,
                'profit': profit,
                'taker': {
                    'id': taker_order.id,
                    'side': taker_order.order_type,
                    'order_id': taker_order.order_id,
                    'maker_order_id': taker_order.maker_order_id,
                    'price': decimal_to_str(taker_order.price()),
                    'quantity': decimal_to_str(taker_order.quantity()),
                    'total': decimal_to_str(taker_order.price() * taker_order.quantity()),
                },
                'maker': {
                    'id': maker_order.id,
                    'side': maker_order.order_type,
                    'order_id': {
                        'tx_hash': maker_order.tx_hash,
                        'tx_output_index': maker_order.tx_output_index,
                    },
                    'price': decimal_to_str(maker_order.price()),
                    'quantity': decimal_to_str(maker_order.quantity()),
                    'total': decimal_to_str(maker_order.price() * maker_order.quantity()),
                }
            })

        maker_taker_pairs = sorted(maker_taker_pairs, key=lambda o: o['created_at'])
        for o in maker_taker_pairs:
            o['created_at'] = arrow.get(o['created_at']).isoformat()
        return maker_taker_pairs

