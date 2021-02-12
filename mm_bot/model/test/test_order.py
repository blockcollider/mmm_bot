from decimal import Decimal

from mm_bot.model.order import MakerOrder, TakerOrder


class TestTakerOrder:
    def test_taker_order(self):
        qty = Decimal('1.234')
        price = Decimal('0.0234')
        order_type = 'buy'
        taker_order = TakerOrder(
            exchange='binance',
            status='open',
            order_type=order_type,
            currency='BTC/ETH',
            order_body={'quantity': str(qty), 'price': price},
            order_id='ee55df98-95d7-409f-a8f0-d8a5bf047acd',
            maker_order_id = 1,
            created_at=None,
            updated_at=None,
        )

        is_buy = order_type == 'buy'

        assert taker_order.quantity() == qty
        assert taker_order.price() == price
        assert taker_order.is_sell() != is_buy
        assert taker_order.is_buy() == is_buy

class TestMakerOrder:
    def test_maker_order(self):
        receives_unit = Decimal('100')
        sends_unit = Decimal('0.01493')
        order_type = 'buy'

        order_from_borderless = {
            "base": 2,
            "collateralizedNrg": "1",
            "deposit": 600,
            "doubleHashedBcAddress": "0x74a9ab94273274e627bb17ec9b18af81f48646a2b62ab58afde3bab11bda9676",
            "fixedUnitFee": "0",
            "isSettled": False,
            "nrgUnit": "1",
            "receivesToAddress": "2570416870016743267L",
            "receivesToChain": "lsk",
            "receivesUnit": str(receives_unit),
            "receivesUnitDenomination": "lsk",
            "sendsFromAddress": "1AJP6ck7XkhhTT7QTrn7U81UczmxgX3Azn",
            "sendsFromChain": "btc",
            "sendsUnit": str(sends_unit),
            "sendsUnitDenomination": "btc",
            "settlement": 300,
            "shiftMaker": 5,
            "shiftTaker": 20,
            "tradeHeight": 51,
            "txHash": "7059fc2763fba359d30b248b243107b7eb7a39909eb5dfff216f157ea53b04c8",
            "txOutputIndex": 0
        }

        utc_now = "2020-02-25T05:43:14"
        maker_order = MakerOrder(
            exchange='borderless',
            currency='LSK/BTC',
            status='open',
            order_type=order_type,
            order_body=order_from_borderless,
            tx_hash=order_from_borderless['txHash'],
            tx_output_index=order_from_borderless['txOutputIndex'],
            block_height=order_from_borderless['tradeHeight'],
            taker_order_body={},
            created_at=utc_now,
            updated_at=utc_now
        )

        assert maker_order.quantity() == receives_unit
        assert maker_order.price() == sends_unit / receives_unit
        assert maker_order.is_buy() == (order_type == 'buy')
