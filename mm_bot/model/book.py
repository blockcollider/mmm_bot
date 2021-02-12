from dataclasses import dataclass
from decimal import Decimal
from typing import List

@dataclass
class PriceLevel:
    price: Decimal
    quantity: Decimal

@dataclass
class OrderBook:
    bid: List[PriceLevel]
    ask: List[PriceLevel]
    # ex BTC/NRG, as you will need to send BTC
    # 1 BTC can buy ? NRG
    bid_nrg_rate: Decimal # only available in borderless
    # ex ETH/NRG, as you will need to send ETH
    ask_nrg_rate: Decimal # only available in borderless
