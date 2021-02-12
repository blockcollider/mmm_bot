import os

import asyncio
import arrow
from decimal import Decimal
from datetime import datetime

from mm_bot.config import config
from mm_bot.model.repository import OrderRepository
from mm_bot.model.order import metadata, MakerOrder, TakerOrder
from mm_bot.model.constants import Status
from mm_bot.helpers import decimal_to_str
from mm_bot.model.constants import Status, OrderType

url = config('database_url', parser=str)
order_repository = OrderRepository(url)

async def main():
    await order_repository._db.execute('delete from taker_orders')
    await order_repository._db.execute('delete from maker_orders')

if __name__ == '__main__':
    asyncio.run(main())
