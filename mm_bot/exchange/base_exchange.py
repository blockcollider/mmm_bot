from typing import List, Tuple
import abc

import mm_bot.model.currency
import mm_bot.model.book
import mm_bot.model.order
import mm_bot.model.constants

class BaseExchange(abc.ABC):
    async def get_account_balance(self):
        pass

    @abc.abstractmethod
    def start(self) -> None:
        """
        Start the loop to pull order book and
        publish new best bid or ask if needed with topic: ('exchange', 'new_best')
        """
        pass

    @abc.abstractmethod
    async def get_order_status(open_orders: List[mm_bot.model.order.Order]) -> Tuple[mm_bot.model.order.Order, mm_bot.model.constants.Status]:
        """
        open_orders: [instance of MakerOrder or TakerOrder]

        return [(order, status), ]
        """
        pass

    @abc.abstractmethod
    async def get_order_book(self, currency: mm_bot.model.currency.CurrencyPair) -> mm_bot.model.book.OrderBook:
        pass


    @abc.abstractmethod
    async def get_open_orders(self) -> List[mm_bot.model.order.Order]:
        """
        Returns list of open orders from the exchange. This is source of truth and
        can be use for bootstrap or updating of current state
        """
        pass

    async def create_orders(self, orders_to_open):
        """
        orders_to_open:
        [{
            'qty': qty,
            'price': best_bid_price_from_maker
        }]
        """
        raise NotImplementedError('required')

    async def cancel_orders(self, orders_to_cancel):
        """
        orders_to_cancel: [instance of MakerOrder or TakerOrder]

        """
        raise NotImplementedError('required')

    def __repr__(self):
        return "{}-{}".format(self.name, self.side)
