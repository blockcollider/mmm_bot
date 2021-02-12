const RpcClient = require('bc-sdk/dist/client').default

const cmdGetLatestBlock = async opts => {
  const {
    bcRpcAddress, bcRpcScookie,
  } = opts

  const client = new RpcClient(bcRpcAddress, bcRpcScookie)

  try {
    const res = await client.getLatestBlock()
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

module.exports = { cmdGetLatestBlock }
