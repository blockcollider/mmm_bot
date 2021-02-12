## Arbitrage


### High level overview

The strategy scans for any arbitrage opportunity by comparing the order books on two exchanges. Whenever it finds any price dislocation between them (i.e. it's profitable to buy from one and sell to the other), it would calculate the optimal order size to do the arbitrage trade, and trades away the price difference by sending opposing orders to both exchanges.

There are two cases:

1, The price of the best `bid` on the `Other Exchange` is higher than the price of the best `ask` on the `Overline interchange`.
```
-- Other Exchange --      --   Overline interchange   --
|------------------|      |------------------|
|                  |      |                  |
|                  |      |                  |
|  Best Bid (100)  |      |                  |
|                  |      |                  |
|                  |      |  Best Ask (98)   |
|------------------|      |------------------|
```

2, The price of the best `ask` on the `Other Exchange` is higher than the price of the best `bid` on the `Overline interchange`.

```
-- Other Exchange --      --   Overline interchange   --
|------------------|      |------------------|
|                  |      |                  |
|                  |      |                  |
|                  |      |  Best Bid (100)  |
|                  |      |                  |
|  Best Ask (98)   |      |                  |
|------------------|      |------------------|
```
In either case, the strategy would create a `sell order` to the exchange with `higher bid` price and create a `buy order` to the exchange with `lower ask` price.
