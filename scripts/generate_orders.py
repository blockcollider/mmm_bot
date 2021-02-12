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
    currency = 'LSK/BTC'
    for i in range(10):
        print(f'Creating order pairs for testing:{i}')
        now = arrow.utcnow()

        tx_hash = '7059fc2763fba359d30b248b243107b7eb7a39909eb5dfff216f157ea53b04c8'
        tx_output_index = 0
        maker_order_body = {'tradeHeight': 51, 'deposit': 600, 'settlement': 300, 'shiftMaker': 5,
                            'shiftTaker': 20, 'sendsFromChain': 'btc', 'receivesToChain': 'lsk',
                            'sendsFromAddress': '1AJP6ck7XkhhTT7QTrn7U81UczmxgX3Azn',
                            'receivesToAddress': '2570416870016743267L', 'sendsUnit': '0.01493',
                            'receivesUnit': '100',
                            'doubleHashedBcAddress': '0x74a9ab94273274e627bb17ec9b18af81f48646a2b62ab58afde3bab11bda9676',
                            'collateralizedNrg': '1', 'nrgUnit': '1',
                            'txHash': tx_hash,
                            'txOutputIndex': tx_output_index, 'isSettled': False, 'fixedUnitFee': '0', 'base': 2,
                            'sendsUnitDenomination': 'btc', 'receivesUnitDenomination': 'lsk'}

        maker_order = MakerOrder(
            exchange='borderless',
            status='filled',
            order_type='buy', # buy LSK/BTC as i receiveToChain is lsk
            currency=currency,
            order_body=maker_order_body,
            tx_hash=tx_hash,
            tx_output_index=tx_output_index,
            block_height='1',
            taker_order_body={},
            created_at=now.datetime,
            updated_at=now.datetime,
            id=None,
        )
        maker_order = await order_repository.create_order(maker_order)
        maker_order_id = maker_order.id

        taker_order_time = now.shift(minutes=10)
        if maker_order.order_type == OrderType.BUY:
            taker_order_type = OrderType.SELL
            taker_price = decimal_to_str(maker_order.price() * Decimal('1.01'))
        else:
            taker_order_type = OrderType.BUY
            taker_price = decimal_to_str(maker_order.price() * Decimal('0.99'))

        taker_order_body = {
            'price': taker_price,
            'quantity': decimal_to_str(maker_order.quantity()),
        }
        taker_order = TakerOrder(
            exchange='binance',
            status='filled',
            order_type=taker_order_type,
            currency=currency,
            order_body=taker_order_body,
            order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
            maker_order_id = maker_order.id,
            created_at=taker_order_time.datetime,
            updated_at=taker_order_time.datetime,
        )
        taker_order = await order_repository.create_order(taker_order)

        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
