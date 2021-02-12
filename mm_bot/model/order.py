from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, TypeVar
import dataclasses

import sqlalchemy

from mm_bot.model.constants import Status, OrderType

metadata = sqlalchemy.MetaData()

MakerOrdersTable = sqlalchemy.Table(
    'maker_orders',
    metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('exchange', sqlalchemy.String),
    sqlalchemy.Column('status', sqlalchemy.String),
    sqlalchemy.Column('order_type', sqlalchemy.String),
    sqlalchemy.Column('currency', sqlalchemy.VARCHAR(255), nullable=False),
    sqlalchemy.Column('order_body', sqlalchemy.JSON),

    sqlalchemy.Column('tx_hash', sqlalchemy.String),
    sqlalchemy.Column('tx_output_index', sqlalchemy.Integer),
    sqlalchemy.Column('block_height', sqlalchemy.String, nullable=True),
    sqlalchemy.Column('taker_order_body', sqlalchemy.JSON),

    sqlalchemy.Column('created_at', sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column('updated_at', sqlalchemy.DateTime, nullable=True),

)

@dataclasses.dataclass
class MakerOrder:
    exchange: str
    status: str
    order_type: str
    currency: str
    order_body: Dict[Any, Any]
    tx_hash: str
    tx_output_index: int
    block_height: str
    taker_order_body: Dict[Any, Any]
    created_at: datetime
    updated_at: datetime
    id: int = None

    IDENTIFIER = 'tx_hash'

    def is_buy(self) -> bool:
        return self.order_type == OrderType.BUY

    def is_sell(self) -> bool:
        return self.order_type == OrderType.SELL

    def price(self) -> Decimal:
        """
        The price of ETH/BTC is 1 ETH worths how many BTC as BTC is quote
        if BUY ETH/BTC, you receive ETH and send BTC
            sendsUnit / receivesUnit
        if SELL ETH/BTC, you receive BTC and send ETH
            receivesUnit / sendsUnit

        Return decimal.Decimal
        """
        sends_unit = Decimal(self.order_body['sendsUnit'])
        receives_unit = Decimal(self.order_body['receivesUnit'])
        if self.is_buy(): # sends BTC and receives ETH
            return sends_unit / receives_unit
        else: # sell
            return receives_unit / sends_unit

    def quantity(self) -> Decimal:
        if self.is_buy(): # sends BTC and receives ETH
            return Decimal(self.order_body['receivesUnit'])
        else: # sell, sends ETH
            return Decimal(self.order_body['sendsUnit'])

    def as_object(self):
        obj = {}
        exclude_fields = {'tx_hash', 'tx_output_index'}
        for field in dataclasses.fields(self):
            key = field.name
            if key in exclude_fields:
                continue

            value = getattr(self, key)
            if type(value) == datetime:
                value = value.replace(microsecond=0).isoformat()

            obj[key] = value

        obj['quantity'] = str(self.quantity())
        obj['price'] = str(self.price())

        return obj


TakerOrdersTable = sqlalchemy.Table(
    'taker_orders',
    metadata,
    sqlalchemy.Column('id', sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column('exchange', sqlalchemy.String),
    sqlalchemy.Column('status', sqlalchemy.String),
    sqlalchemy.Column('order_type', sqlalchemy.String),
    sqlalchemy.Column('currency', sqlalchemy.VARCHAR(255), nullable=False),
    sqlalchemy.Column('order_body', sqlalchemy.JSON),
    sqlalchemy.Column('order_id', sqlalchemy.String),
    sqlalchemy.Column('maker_order_id', sqlalchemy.Integer),

    sqlalchemy.Column('created_at', sqlalchemy.DateTime, nullable=True),
    sqlalchemy.Column('updated_at', sqlalchemy.DateTime, nullable=True),
)

@dataclasses.dataclass
class TakerOrder:
    exchange: str
    status: str
    order_type: str
    currency: str
    order_body: Dict[Any, Any]
    order_id: str
    maker_order_id: int
    created_at: datetime
    updated_at: datetime
    id: int = None

    IDENTIFIER = 'order_id'

    def is_buy(self) -> bool:
        return self.order_type == OrderType.BUY

    def is_sell(self) -> bool:
        return self.order_type == OrderType.SELL

    def price(self) -> Decimal:
        """
        Return decimal.Decimal
        """
        return Decimal(self.order_body['price'])

    def quantity(self) -> Decimal:
        return Decimal(self.order_body['quantity'])

    def as_object(self):
        obj = {}
        exclude_fields = {'order_body'}
        for field in dataclasses.fields(self):
            key = field.name
            if key in exclude_fields:
                continue

            value = getattr(self, key)
            if type(value) == datetime:
                value = value.replace(microsecond=0).isoformat()

            obj[key] = value

        obj['quantity'] = str(self.quantity())
        obj['price'] = str(self.price())

        return obj

Order = TypeVar('Order', MakerOrder, TakerOrder)
