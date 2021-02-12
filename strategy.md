## Cross Exchange Strategy


### High Level Overview

The MMM bot is built on the assumption that there are inefficient markets, which is a logical occurrence that happens when comparing custodial exchanges to truly decentralized markets. When interacting with these markets, there is more liquidity in the taker exchanges with smaller bid-ask spread and less liquidity in the maker exchange with larger bid-ask spread.

```
-- Taker Exchange --      -- Maker Exchange --
|------------------|      |------------------|
|                  |      |  Best Ask(102)   |
|  Best Ask (101)  |      |                  |
|                  |      |                  |
|  Best Bid (99)   |      |                  |
|                  |      |  Best Bid (98)   |
|------------------|      |------------------|
```

There are two types of orders: `buy order` and `sell order` in the maker exchange.

1. Buy order. The Bot creates a limit buy order on the maker exchange. Once this order is filled, it immediately creates an opposite sell order in the taker exchange.

   **This requires the `Price(bid, taker exchange) > Price(bid, maker exchange)`
   when opening a buy order in the maker exchange**

   For example, in the above runbook, you can create a limit **buy** order with
   `98.1` in the maker exchange. Once it is filled, you immediately create
   a **sell** order in the taker exchange at `99`.

2. Sell order. Bot creates a limit sell order in the maker exchange. Once this
   order is filled, it immediately creates an opposite buy order in the taker exchange.

    **This requires the `Price(ask, taker exchange) < Price(ask, maker exchange)`
   when opening a buy order in the maker exchange**

   For example, in the above runbook, you can create a limit **sell** order with
   `101.9` in the maker exchange. Once it is filled, you immediately create
   a **buy** order in the taker exchange at `101`.


There are two an infinite loops. One loop is in charge of create orders if
needed, inside this loop:
  1. Adjust open maker orders.
     1. Check the profit_rate to decide whether to cancel the order
  2. Create maker orders when the potential profit is above the target profit
     level. The order can be buy order or sell order
  3. Load all filled maker orders and create corresponding taker orders

The other loop is to check order status and update the state in the local db.
For the maker exchange (borderless), not only does it checks the order
status, but also 1) auto-unlock collateralized nrg 2) sent underlying assets if
the maker tx is still in its settlement window.
