from decimal import Decimal

from mm_bot.model.currency import CurrencyPair

def test_to_currency():
    base = 'LSK'
    counter = 'BTC'

    pair = CurrencyPair(base, counter)

    assert pair.to_currency() == 'LSK/BTC'

    assert pair.to_currency(exchange='binance') == 'LSKBTC'

    assert CurrencyPair('WAV', 'BTC').to_currency(exchange='binance') == 'WAVESBTC'
    assert CurrencyPair('WAV', 'BTC').to_currency(exchange='borderless') == 'WAV/BTC'

