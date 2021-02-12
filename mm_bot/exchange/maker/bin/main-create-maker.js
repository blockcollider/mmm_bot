const RpcClient = require('bc-sdk/dist/client').default
const Wallet = require('bc-sdk/dist/wallet').default

const {
  createMakerOrderTransaction,
} = require('bc-sdk/dist/transaction')

const makerOrderParams = [
  'shiftMaker',
  'shiftTaker',
  'depositLength',
  'settleLength',
  'sendsFromChain',
  'receivesToChain',
  'sendsFromAddress',
  'receivesToAddress',
  'sendsUnit',
  'receivesUnit',
  'bcAddress',
  'bcPrivateKeyHex',
  'collateralizedNrg',
  'nrgUnit',
  'additionalTxFee',
]

const cmdCreateMaker = async opts => {
  for (const param of makerOrderParams) {
    if (!(param in opts)) {
      process.stderr.write(`You have to provide --${param}\n`)
      process.exit(1)
    }
  }

  const {
    bcRpcAddress, bcRpcScookie,
    sendsFromChain, receivesToChain,
    sendsFromAddress, receivesToAddress,
    sendsUnit, receivesUnit,
    bcAddress, bcPrivateKeyHex,
    collateralizedNrg, nrgUnit, additionalTxFee,
  } = opts

  let {
    shiftMaker, shiftTaker, depositLength, settleLength,
  } = opts
  shiftMaker = parseInt(shiftMaker, 10)
  shiftTaker = parseInt(shiftTaker, 10)
  depositLength = parseInt(depositLength, 10)
  settleLength = parseInt(settleLength, 10)

  try {
    const res = await onCreateMakerTx (
      bcRpcAddress, bcRpcScookie,
      shiftMaker, shiftTaker, depositLength, settleLength,
      sendsFromChain, receivesToChain,
      sendsFromAddress, receivesToAddress,
      sendsUnit, receivesUnit,
      bcAddress, bcPrivateKeyHex,
      collateralizedNrg, nrgUnit, additionalTxFee,
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

async function onCreateMakerTx (
  bcRpcAddress, bcRpcScookie,
  shiftMaker, shiftTaker, depositLength, settleLength,
  sendsFromChain, receivesToChain,
  sendsFromAddress, receivesToAddress,
  sendsUnit, receivesUnit,
  bcAddress, bcPrivateKeyHex,
  collateralizedNrg, nrgUnit, additionalTxFee,
) {
  // fixedUnitFee has to be ''
  const fixedUnitFee = ''
  const client = new RpcClient(bcRpcAddress, bcRpcScookie)
  const wallet = new Wallet(client)

  const spendableOutpointsList = await wallet.getSpendableOutpoints(bcAddress)

  const tx = createMakerOrderTransaction(
    spendableOutpointsList,
    shiftMaker, shiftTaker, depositLength, settleLength,
    sendsFromChain, receivesToChain,
    sendsFromAddress, receivesToAddress,
    sendsUnit, receivesUnit,
    bcAddress, bcPrivateKeyHex,
    collateralizedNrg, nrgUnit, fixedUnitFee, additionalTxFee,
  )
  const res = await client.sendTx(tx)
  return res
}

module.exports = { cmdCreateMaker }
