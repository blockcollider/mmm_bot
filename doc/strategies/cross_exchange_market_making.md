## Cross Exchange Strategy


### High level overview

The MMM bot is built on the assumption that there are inefficient markets, which is a logical occurrence that happens when comparing custodial exchanges to truly decentralized markets. When interacting with these markets, there is more liquidity in the taker exchanges with smaller bid-ask spread and less liquidity in the maker exchange with larger bid-ask spread.

The MMM bot makes profits by creating maker orders in the maker exchange and then creating opposite orders in the taker exchange once orders in the maker exchange are taken. The profit is the price difference of best bid or best ask in two exchanges times the trading volume.
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

1. **Buy order in the maker exchange**. The Bot creates a limit buy order on the maker exchange. Once this order is filled, it immediately creates an opposite sell order in the taker exchange.

   **This requires the `Price(bid, taker exchange) > Price(bid, maker exchange)`
   when opening a buy order in the maker exchange**

   For example, in the above runbook, you can create a limit **buy** order with
   `98.1` in the maker exchange. Once it is filled, you immediately create
   a **sell** order in the taker exchange at `99`.

2. **Sell order in the taker exchange**. Bot creates a limit sell order in the maker exchange. Once this
   order is filled, it immediately creates an opposite buy order in the taker exchange.

    **This requires the `Price(ask, taker exchange) < Price(ask, maker exchange)`
   when opening a buy order in the maker exchange**

   For example, in the above runbook, you can create a limit **sell** order with
   `101.9` in the maker exchange. Once it is filled, you immediately create
   a **buy** order in the taker exchange at `101`.

In the context of this MMM Bot, the maker exchange is the **Overline interchange** and taker exchange is the **Binance**.

There are two loops in this strategy.

One loop is in charge of create orders if
needed either in the `interchange` or `Binance`, inside this loop:
  1. Adjust open orders in the `interchange` if needed
     1. Check the profit_rate to decide whether to cancel the order
  2. Create maker orders when the potential profit is above the target profit
     level. The order can be either buy or sell
  3. Load all filled maker orders and create corresponding taker orders

The other loop is charge of settling orders in the `interchange`, inside the loop:
   1. check orders status and update the state in the local db.
   2. For orders in `interchange`, it checks any expired orders and auto-unlock collaterals
   3. For orders in `Binance`, it sends underlying assets to the taker in the interchange when an order is filled in the Binance (it only tries to send it when the maker tx is still in its settlement window)

### Take `ETH/BTC` as an example, let's say its price is:

```
-- Binance          --      -- Overline interchange     --
|------------------|      |------------------|
|                  |      |  Best Ask(0.06)  |
|  Best Ask (0.05) |      |                  |
|                  |      |                  |
|  Best Bid (0.04) |      |                  |
|                  |      |  Best Bid (0.03) |
|------------------|      |------------------|
```

You start the MMM bot and it will do:
1. Create a **Buy** order of `ETH/BTC` with price as `0.031` and quantity as `1 ETH` (as an example)
2. Wait until this order is filled. Once filled:

    a. The taker of this order will send `1 ETH` to the `ETH` wallet configured in the bot, which is your `ETH` wallet address in its Binance account.

    b. The bot will also need to send `0.031 BTC` to this taker's `BTC` wallet. However **the bot does not send it now**

3. Create a **SELL** order of `ETH/BTC` with price as `0.04` and quantity is `1 ETH`. Since the taker in the step `2.a` sends the `1 ETH` to your `ETH` wallet in the Binance, your `ETH` keeps the same. In this case, your profit is `(0.04 - 0.031) BTC` before any transaction cost.
4. Now that your **SELL** order of `ETH/BTC` in Binance is filled, the bot will transfer `0.031 BTC` to the taker on the Overline interchange (in step `2.b`) to settle the trade.
