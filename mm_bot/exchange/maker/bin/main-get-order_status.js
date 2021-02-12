const fs = require('fs')
const RpcClient = require('bc-sdk/dist/client').default
const bc = require('bc-sdk/dist/protos/bc_pb')
const { toASM } = require('bc-sdk/dist/script/bytecode')

const cmdGetOrderStatus = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
    txHash
  } = opts

  if (!txHash) {
    process.stderr.write(`You have to provide --txHash\n`)
    process.exit(1)
  }

  let {
    txOutputIndex
  } = opts

  if (!Number.isInteger(txOutputIndex)) {
    process.stderr.write(`You have to provide --txOutputIndex\n`)
    process.exit(1)
  }
  txOutputIndex = parseInt(txOutputIndex)

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)

  try {
    const req = new bc.GetOutPointRequest()
    req.setHash(txHash)
    req.setIndex(txOutputIndex)

    const res = await client.getTxClaimedBy(req)
    if (res.code && res.message) {
      process.stderr.write(res.message + "\n")
      process.exit(1)
    }
    // res is Transaction.AsObject()
    // if outPoint is not taken by taker, res is an empty Transaction
    const output = {}
    if (res['hash'].length === 0) {
      output['taken'] = false
    } else {
      output['taken'] = true
      const taker = {
        'txHash': res['hash'],
        'sendsFromAddress': '',
        'receivesToAddress': '',
      }
      for (let input of res['inputsList']) {
        if (input['outPoint']['hash'] === txHash && input['outPoint']['index'] === txOutputIndex) {
          const decodedScript = toASM(Buffer.from(input['inputScript'], 'base64'), 0x01)
          const sendsFromAddress = decodedScript.split(' ')[0]
          const receivesToAddress = decodedScript.split(' ')[1]

          taker['sendsFromAddress'] = sendsFromAddress
          taker['receivesToAddress'] = receivesToAddress
        }
      }
      output['taker'] = taker
    }
    process.stdout.write(JSON.stringify(output))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdGetOrderStatus }
