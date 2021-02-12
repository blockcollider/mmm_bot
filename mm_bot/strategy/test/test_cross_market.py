import unittest.mock
from decimal import Decimal
import asyncio

import aiopubsub.testing.mocks
import asynctest
import pytest

from mm_bot.strategy.cross_market import CrossMarketStrategy
from mm_bot.exchange.maker.borderless import Borderless
from mm_bot.exchange.taker.binance import Binance
from mm_bot.model.currency import CurrencyPair
from mm_bot.model.book import OrderBook, PriceLevel
from mm_bot.model.repository import OrderRepository

@pytest.fixture
def hub(event_loop): # pylint: disable=unused-argument
    return aiopubsub.testing.mocks.MockHub()


@pytest.fixture
def binance():
    b = asynctest.Mock(Binance)
    b.name = 'binance'
    b.side = 'taker'
    b.min_total_order_value = {
        'ETH': Decimal('0.011'),  # 0.01
        'BTC': Decimal('0.00011'),  # 0.0001
        'USDT': Decimal('11'),  # 1mm_bot/strategy/test/test_cross_market.py0
    }
    return b


@pytest.fixture
def borderless():
    b = asynctest.Mock(Borderless)
    b.name = 'borderless'
    b.side = 'maker'
    return b


@pytest.fixture
def order_repository():
    return asynctest.Mock(OrderRepository)


@pytest.mark.asyncio
async def test_instance(hub, order_repository, binance, borderless):
    s = CrossMarketStrategy(
        hub, order_repository,
        binance, borderless,
        CurrencyPair('LSK', 'BTC'),
        0, Decimal(0), Decimal(0), Decimal(0), False
    )

    assert isinstance(s, CrossMarketStrategy)


@pytest.mark.asyncio
async def test_single_step(caplog, order_repository, hub, binance, borderless):
    caplog.set_level(__import__('logging').DEBUG)
    max_open_orders = 3
    min_profitability_rate = Decimal('0.01')
    max_qty_per_order = Decimal('0.1')
    cancel_order_threshold = Decimal('0.005')

    s = CrossMarketStrategy(
        hub, order_repository,
        binance, borderless,
        CurrencyPair('LSK', 'BTC'),
        max_open_orders, min_profitability_rate, max_qty_per_order, cancel_order_threshold, False
    )

    ob_binance_1 = OrderBook(
        [PriceLevel(Decimal('1.6'), Decimal('100'))], # bid
        [PriceLevel(Decimal('1.7'), Decimal('250'))], # ask
        0, 0
    )

    ob_borderless_1 = OrderBook(
        [PriceLevel(Decimal('1.5'), Decimal('100'))], # bid
        [PriceLevel(Decimal('1.6'), Decimal('250'))], # ask
        Decimal('10.1'), Decimal('9.8')
    )

    s.start()

    order_repository.count_open_orders.side_effect = [0, 0]
    # update with first state of both orderbooks
    s._update_order_book('binance', ob_binance_1)
    s._update_order_book('borderless', ob_borderless_1)
    await s._recalculate_and_recreate_orders()

    # order was create on borderless but not on binance
    assert borderless.create_orders.call_count == 1
    created_order = borderless.create_orders.call_args[0][0][0]
    assert created_order['order_type'] == 'buy'
    assert created_order['price'] == Decimal('1.5')
    borderless.create_orders.reset_mock()

    ob_borderless_2 = OrderBook(
        [
            PriceLevel(Decimal('1.7'), Decimal('50')),
            PriceLevel(Decimal('1.6'), Decimal('100'))
            ], # bid
        [PriceLevel(Decimal('1.8'), Decimal('250'))], # ask
        Decimal('10.1'), Decimal('9.8')
    )

    order_repository.count_open_orders.side_effect = [1, 0]
    # new order book came on borderless
    s._update_order_book('borderless', ob_borderless_2)
    await s._recalculate_and_recreate_orders()

    # orders were not created on borderless again (call count is from previous OB update)
    assert borderless.create_orders.call_count == 1
    created_order = borderless.create_orders.call_args[0][0][0]
    assert created_order['order_type'] == 'sell'
    assert created_order['price'] == Decimal('1.8')
    assert binance.create_orders.call_count == 0
    borderless.create_orders.reset_mock()

    ob_binance_2 = OrderBook(
        [PriceLevel(Decimal('1.6'), Decimal('10'))], # bid
        [PriceLevel(Decimal('1.5'), Decimal('20'))], # ask
        0, 0
    )

    order_repository.count_open_orders.side_effect = [2, 0]
    # new ask best on binance is <= ask best on borderless
    s._update_order_book('borderless', ob_borderless_2)
    await s._recalculate_and_recreate_orders()

    # orders were not created on borderless again (call count is from previous OB update)
    assert borderless.create_orders.call_count == 1
    created_order = borderless.create_orders.call_args[0][0][0]
    assert created_order['order_type'] == 'sell'
    assert created_order['price'] == Decimal('1.8')
    assert binance.create_orders.call_count == 0
    borderless.create_orders.reset_mock()

    await s.stop()
