from enum import Enum

class Exchange:
    BORDERLESS = 'borderless'
    BINANCE = 'binance'

class Status:
    OPEN = 'open'
    CANCELED = 'canceled'
    FILLED = 'filled'
    SETTLED = 'settled'
    EXPIRED = 'expired'

class OrderType:
    BUY = 'buy'
    SELL = 'sell'

class SupportedCurrency(Enum):
    BTC = 1
    ETH = 2
    LSK = 3
    NEO = 4
    WAV = 5
    DAI = 6
    USDT = 7

class SupportedCounterCurrency(Enum):
    BTC = 1
    ETH = 2
    USDT = 3

"""

time
pair: 'ETH/BTC'
order_type: ''

"""
