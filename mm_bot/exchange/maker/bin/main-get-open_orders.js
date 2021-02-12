const fs = require('fs')
const RpcClient = require('bc-sdk/dist/client').default
const bc = require('bc-sdk/dist/protos/bc_pb')
const { Currency, CurrencyInfo } = require('bc-sdk/dist/utils/coin')

const cmdGetOpenOrders = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
    bcAddress
  } = opts

  if (!bcAddress) {
    process.stderr.write(`You have to provide --bcAddress\n`)
    process.exit(1)
  }

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)

  try {
    const latestBlock = await client.getLatestBlock()

    const req = new bc.GetSpendableCollateralRequest()
    req.setAddress(bcAddress.toLowerCase())
    req.setTo(1000)
    req.setFrom(0) // from is smaller than to

    const res = await client.getOpenOrders(req)
    if (res.code && res.message) {
      process.stderr.write(res.message + "\n")
      process.exit(1)
    }
    const ordersList = []
    res.ordersList.forEach((o) => {
      if((o.tradeHeight + o.deposit > latestBlock.height)){
        ordersList.push(o)
      }
    })

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
    process.stdout.write(JSON.stringify(ordersList))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdGetOpenOrders }
