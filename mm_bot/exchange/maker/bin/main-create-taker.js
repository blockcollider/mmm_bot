const RpcClient = require('bc-sdk/dist/client').default
const Wallet = require('bc-sdk/dist/wallet').default

const {
  createTakerOrderTransaction,
} = require('bc-sdk/dist/transaction')

const takerOrderParams = [
  'makerOrderBase', 'makerOrderFixedUnitFee',
  'makerOrderDoubleHashedBcAddress',
  'makerOrderNrgUnit',
  'makerOrderCollateralizedNrg',
  'makerOrderHash',
  'makerOrderTxOutputIndex',
  'sendsFromAddress',
  'receivesToAddress' ,
  'bcAddress',
  'bcPrivateKeyHex' ,
  'collateralizedNrg',
  'additionalTxFee',
]
const cmdCreateTaker = async opts => {
  for (const param of takerOrderParams) {
    if (!(param in opts)) {
      process.stderr.write(`You have to provide --${param}\n`)
      process.exit(1)
    }
  }

  const {
    bcRpcAddress, bcRpcScookie,
    makerOrderBase, makerOrderFixedUnitFee,
    makerOrderDoubleHashedBcAddress, makerOrderNrgUnit, makerOrderCollateralizedNrg,
    makerOrderHash,
    sendsFromAddress, receivesToAddress,
    bcAddress, bcPrivateKeyHex,
    collateralizedNrg, additionalTxFee,
  } = opts
  let {
    makerOrderTxOutputIndex,
  } = opts
  makerOrderTxOutputIndex = parseInt(makerOrderTxOutputIndex)

  try {
    const res = await onCreateTakerTx (
      bcRpcAddress, bcRpcScookie,
      makerOrderBase, makerOrderFixedUnitFee,
      makerOrderDoubleHashedBcAddress, makerOrderNrgUnit, makerOrderCollateralizedNrg,
      makerOrderHash, makerOrderTxOutputIndex,
      sendsFromAddress, receivesToAddress,
      bcAddress, bcPrivateKeyHex,
      collateralizedNrg, additionalTxFee,
    )
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

async function onCreateTakerTx (
   bcRpcAddress, bcRpcScookie,
   makerOrderBase, makerOrderFixedUnitFee,
   makerOrderDoubleHashedBcAddress, makerOrderNrgUnit, makerOrderCollateralizedNrg,
   makerOrderHash, makerOrderTxOutputIndex,
   sendsFromAddress, receivesToAddress,
   bcAddress, bcPrivateKeyHex,
   collateralizedNrg, additionalTxFee,
) {
  const client = new RpcClient(bcRpcAddress, bcRpcScookie)
  const wallet = new Wallet(client)

  const spendableOutpointsList = await wallet.getSpendableOutpoints(bcAddress)
  const makerOpenOrder = {
    base: makerOrderBase,
    doubleHashedBcAddress: makerOrderDoubleHashedBcAddress,
    collateralizedNrg: makerOrderCollateralizedNrg,
    nrgUnit: makerOrderNrgUnit,
    fixedUnitFee: makerOrderFixedUnitFee,
    txHash: makerOrderHash,
    txOutputIndex: makerOrderTxOutputIndex
  }

  const tx = createTakerOrderTransaction(
    spendableOutpointsList,
    sendsFromAddress, receivesToAddress,
    makerOpenOrder,
    bcAddress, bcPrivateKeyHex,
    collateralizedNrg, additionalTxFee,
  )
  const res = await client.sendTx(tx)
  return res
}

module.exports = { cmdCreateTaker }
