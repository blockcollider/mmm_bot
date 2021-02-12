const allAssetsTransfer = require('bc-sdk/dist/transfers')

const cmdTransferAsset = async opts => {
  const requiredParams = [
    'assetId',
    'privateKey',
    'from',
    'to',
    'amount'
  ]
  for (const param of requiredParams) {
    if (!(param in opts)) {
      process.stderr.write(`You have to provide --${param}\n`)
      process.exit(1)
    }
  }
  const {
    assetId,
    privateKey, from, to
  } = opts
  let {
    amount
  } = opts
  amount = parseFloat(amount)

  const transferFn = allAssetsTransfer[`transfer${assetId.toUpperCase()}`]

  if (!transferFn) {
    process.stderr.write(`Invalid assetId: ${assetId}`)
    process.exit(1)
  }

  try{
    const res = await transferFn(privateKey, from, to, amount)

    process.stdout.write(JSON.stringify(res))
  } catch (e) {
    process.stderr.write(e.toString() + "\n")
    process.exit(1)
  }
}

module.exports = { cmdTransferAsset }
