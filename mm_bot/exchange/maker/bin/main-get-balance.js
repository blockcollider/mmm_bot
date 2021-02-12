const RpcClient = require('bc-sdk/dist/client').default
const Wallet = require('bc-sdk/dist/wallet').default

const {
  createTakerOrderTransaction,
} = require('bc-sdk/dist/transaction')

const cmdGetBalance = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
    bcAddress
  } = opts

  if (!bcAddress) {
    process.stderr.write(`You have to provide --bcAddress\n`)
    process.exit(1)
  }

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)
  const wallet = new Wallet(client)

  try {
    const res = await wallet.getBalance(bcAddress)
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

module.exports = { cmdGetBalance }
