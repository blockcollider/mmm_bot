import pytest
import aiopubsub.testing.mocks
from decimal import Decimal

from mm_bot.exchange.taker.binance import Binance
from mm_bot.model.currency import CurrencyPair
from mm_bot.model.book import OrderBook, PriceLevel

@pytest.fixture
def hub(event_loop): # pylint: disable=unused-argument
    return aiopubsub.testing.mocks.MockHub()

@pytest.mark.asyncio
async def test_should_publish_change(hub):
    b = Binance(hub, CurrencyPair('A', 'B'), 2, 'a', 'b')

    new_ob = OrderBook(
        [
            PriceLevel(Decimal('0.01956200'), Decimal('14.08700000')),
            PriceLevel(Decimal('0.01946100'), Decimal('4.00000000'))
            ],
        [
            PriceLevel(Decimal('0.01996500'), Decimal('0.60700000')),
            PriceLevel(Decimal('0.02976600'), Decimal('4.00000000'))
            ],
        Decimal(0), Decimal(0)
        )
    assert b._should_publish_change(new_ob)

    b._last_bid_best = PriceLevel(Decimal('0.01956200'), Decimal('14.08700000'))
    b._last_ask_best = PriceLevel(Decimal('0.01996500'), Decimal('0.60700000'))

    assert not b._should_publish_change(new_ob)

    # change best bid, now _should_publish_change should signal update needed
    new_ob.bid[0] = PriceLevel(Decimal('0.01956300'), Decimal('0.01'))

    assert b._should_publish_change(new_ob)
    assert not b._should_publish_change(new_ob)

    await b.stop()
