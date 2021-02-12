const RpcClient = require('bc-sdk/dist/client').default
const Wallet = require('bc-sdk/dist/wallet').default

const {
  createUnlockTakerTx
} = require('bc-sdk/dist/transaction')

const unlockOrderParams = [
  'txHash',
  'txOutputIndex',
  'bcAddress',
  'bcPrivateKeyHex' ,
]
const cmdCreateUnlock = async opts => {
  for (const param of unlockOrderParams) {
    if (!(param in opts)) {
      process.stderr.write(`You have to provide --${param}\n`)
      process.exit(1)
    }
  }

  const {
    bcRpcAddress, bcRpcScookie,
    txHash,
    bcAddress, bcPrivateKeyHex,
  } = opts
  let {
    txOutputIndex,
  } = opts
  txOutputIndex = parseInt(txOutputIndex)

  try {
    const client = new RpcClient(bcRpcAddress, bcRpcScookie)

    const tx = await createUnlockTakerTx(
      txHash, txOutputIndex.toString(),
      bcAddress, bcPrivateKeyHex,
      client
    )

    const res = await client.sendTx(tx)

    if (res.code && res.message) {
      process.stderr.write(res.message + "\n")
      process.exit(1)
    }
    process.stdout.write(JSON.stringify(res))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }

}

module.exports = { cmdCreateUnlock }
