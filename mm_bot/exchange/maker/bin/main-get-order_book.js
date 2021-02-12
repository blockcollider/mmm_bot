const fs = require('fs')
const RpcClient = require('bc-sdk/dist/client').default
const core = require('bc-sdk/dist/protos/core_pb')
const { Currency, CurrencyInfo } = require('bc-sdk/dist/utils/coin')

const cmdGetOrderBook = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
    outputFile,
  } = opts

  let out

  if (outputFile) {
    out = fs.createWriteStream(outputFile)
  } else {
    out = process.stdout
  }

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)

  try {
    const res = await client.getOpenOrders(new core.Null())
    if (res.code && res.message) {
      process.stderr.write(res.message + "\n")
      process.exit(1)
    }
    // the sendsUnit and receivesUnit in the ordersList are in the indivisible
    // unit, we want to convert it back
    const ordersList = res.ordersList
    for (let order of ordersList) {
      order.sendsUnit = Currency.fromMinimumUnitToHuman(
        order.sendsFromChain, order.sendsUnit, CurrencyInfo[order.sendsFromChain].minUnit
      )
      order.sendsUnitDenomination = CurrencyInfo[order.sendsFromChain].humanUnit

      order.receivesUnit = Currency.fromMinimumUnitToHuman(
        order.receivesToChain, order.receivesUnit, CurrencyInfo[order.receivesToChain].minUnit
      )
      order.receivesUnitDenomination = CurrencyInfo[order.receivesToChain].humanUnit
    }
    out.write(JSON.stringify(ordersList))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdGetOrderBook }
