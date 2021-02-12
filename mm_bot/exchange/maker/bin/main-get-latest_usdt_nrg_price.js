const fs = require('fs')
const RpcClient = require('bc-sdk/dist/client').default
const core = require('bc-sdk/dist/protos/core_pb')
const bc = require('bc-sdk/dist/protos/bc_pb')
const { toASM } = require('bc-sdk/dist/script/bytecode')
const { Currency, CurrencyInfo } = require('bc-sdk/dist/utils/coin')

const pair = ['nrg', 'usdt'] // usdt/nrg

function findUsdtNrgPrice(orders) {
  let price = -1
  for (let order of orders) {
    const maker = order.maker
    if (pair.includes(maker.sendsFromChain) && pair.includes(maker.receivesToChain)) {
      sendsUnit = Currency.fromMinimumUnitToHuman(
        maker.sendsFromChain, maker.sendsUnit, CurrencyInfo[maker.sendsFromChain].minUnit
      )
      receivesUnit = Currency.fromMinimumUnitToHuman(
        maker.receivesToChain, maker.receivesUnit, CurrencyInfo[maker.receivesToChain].minUnit
      )

      if (maker.receivesToChain == 'usdt') { // buy
        price = parseFloat(sendsUnit) / parseFloat(receivesUnit)
      } else {
        price = parseFloat(receivesUnit) / parseFloat(sendsUnit)
      }
      break
    }
  }

  return price
}

const cmdGetLatestUsdtNrgPrice = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
  } = opts

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)

  let price = -1
  try {
    let data = await client.makeJsonRpcRequest('getHistoricalOrders',['latest', 5000])
    // TOOD: refactor this
    if(data && data.ordersList){
      let orders = data.ordersList;
      price = findUsdtNrgPrice(orders)
      if (price === -1) {
          while(data.nextBlock){
            // console.log(`getHistoricalOrders`,data.nextBlock)
            data = await client.makeJsonRpcRequest('getHistoricalOrders',[data.nextBlock.toString(), 1000])
            // console.log({data})
            if(data && data.ordersList) {
              price = findUsdtNrgPrice(data.ordersList)
            }
            if (price !== -1) {
              break
            }
          }
      }
    }
    if (price === -1) {
      // No history price, try to get the current orders
      const res = await client.getOpenOrders(new core.Null())
      if (res.code && res.message) {
        price = -1
      } else {
        const ordersList = res.ordersList
        for (let order of ordersList) {
          if (pair.includes(order.sendsFromChain) && pair.includes(order.receivesToChain)) {
            order.sendsUnit = Currency.fromMinimumUnitToHuman(
              order.sendsFromChain, order.sendsUnit, CurrencyInfo[order.sendsFromChain].minUnit
            )
            order.receivesUnit = Currency.fromMinimumUnitToHuman(
              order.receivesToChain, order.receivesUnit, CurrencyInfo[order.receivesToChain].minUnit
            )

            let newPrice;
            if (order.receivesToChain == 'usdt') { // buy
              newPrice = parseFloat(order.sendsUnit) / parseFloat(order.receivesUnit)
            } else {
              newPrice = parseFloat(order.receivesUnit) / parseFloat(order.sendsUnit)
            }

            if (price === -1) {
              price = newPrice
            } else {
              price = Math.min(price, newPrice)
            }
          }
        }
      }
    }

    if (price === -1) {
      // Neither current orders nor historical orders, use fallback
      // set 1 NRG = 1 USDT
      price = 1
    }

    process.stdout.write(JSON.stringify({'price': price}))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdGetLatestUsdtNrgPrice }
