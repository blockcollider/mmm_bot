from dataclasses import dataclass

@dataclass
class CurrencyPair:
    """
    for LSK/BTC, base is LSK, counter is BTC
    """
    base: str
    counter: str

    def __str__(self):
        return self.to_currency()

    def to_currency(self, exchange='borderless'):
        if exchange == 'binance':
            b = self.base
            if b == 'WAV':
                b = 'WAVES'
            return f'{b}{self.counter}'
        return f'{self.base}/{self.counter}'
