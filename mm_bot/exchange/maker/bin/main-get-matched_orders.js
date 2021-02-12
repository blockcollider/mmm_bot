const fs = require('fs')
const RpcClient = require('bc-sdk/dist/client').default
const bc = require('bc-sdk/dist/protos/bc_pb')
const { Currency, CurrencyInfo } = require('bc-sdk/dist/utils/coin')

const cmdGetMatchedOrders = async opts => {
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
    const req = new bc.GetBalanceRequest()
    req.setAddress(bcAddress.toLowerCase())

    const res = await client.makeJsonRpcRequest('getMatchedOrders', req.toArray())

    if (res.code && res.message) {
      process.stderr.write(res.message + "\n")
      process.exit(1)
    }
    process.stdout.write(JSON.stringify(res.ordersList))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdGetMatchedOrders }
