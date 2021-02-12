from decimal import Decimal

from mm_bot.model.book import PriceLevel

def test_price_level_eq():
    """
    Is here mainly for illustrating, that PriceLevel's generated __eq__ works as we expect
    """
    pl1 = PriceLevel(Decimal('0.01'), Decimal('0.01'))
    pl2 = PriceLevel(Decimal('0.01'), Decimal('0.01'))

    assert pl1 == pl2

    pl2.price = Decimal('0.02')

    assert pl1 != pl2

    pl2.price = pl1.price
    pl2.quantity = Decimal('1.01')
    assert pl1 != pl2
