process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0'
const minimist = require('minimist')

const { cmdGetOpenOrders } = require('./main-get-open_orders')
const { cmdGetOrderBook } = require('./main-get-order_book')
const { cmdGetOrderStatus } = require('./main-get-order_status')
const { cmdGetLatestUsdtNrgPrice } = require('./main-get-latest_usdt_nrg_price')
const { cmdGetBalance } = require('./main-get-balance')
const { cmdGetUnmatchedOrders } = require('./main-get-unmatched_orders')
const { cmdGetMatchedOrders } = require('./main-get-matched_orders')
const { cmdCreateTaker } = require('./main-create-taker')
const { cmdCreateUnlock } = require('./main-create-unlock')
const { cmdCreateMaker } = require('./main-create-maker')
const { cmdTransferAsset } = require('./main-transfer-asset')
const { cmdGetLatestBlock } = require('./main-get-latest_block')

const argv = minimist(process.argv.slice(2),
  {
    string: [
      'bcRpcScookie',
      'bcAddress', 'txHash', 'bcPrivateKeyHex',
      'sendsUnit', 'receivesUnit',
      'additionalTxFee',
      'nrgUnit', 'collateralizedNrg',
      'makerOrderNrgUnit', 'makerOrderCollateralizedNrg',
      'makerOrderDoubleHashedBcAddress',
      'sendsFromChain', 'receivesToChain',
      'sendsFromAddress', 'receivesToAddress',
      'from', 'to', 'privateKey', 'assetId',
    ]
  }
)

if (!argv.bcRpcAddress || !argv.bcRpcScookie) {
  process.stderr.write(`You have to provide both --bcRpcAddress and --bcRpcScookie\n`)
  process.exit(1)
}

const [cmd, subCmd] = argv._

/*
 * create
 *   maker
 *   taker
 *   transfer
 *   unlock
 * cancel
 *   maker
 * get
 *   balance
 *   latest_block
 *   open_orders
 *   order_books
 *   order_status
 *   latest_usdt_nrg_price
 * transfer
 *   btc|eth|...
 *
 */
const RUNNERS = {
  get: {
    balance: cmdGetBalance,
    latest_block: cmdGetLatestBlock,
    open_orders: cmdGetOpenOrders,
    order_book: cmdGetOrderBook,
    order_status: cmdGetOrderStatus,
    unmatched_orders: cmdGetUnmatchedOrders,
    matched_orders: cmdGetMatchedOrders,
    latest_usdt_nrg_price: cmdGetLatestUsdtNrgPrice,
  },
  create: {
    taker: cmdCreateTaker,
    maker: cmdCreateMaker,
    unlock: cmdCreateUnlock,
  },
  cancel: {
    maker: cmdCreateTaker
  },
  transfer: {
    asset: cmdTransferAsset
  }
}

if (!RUNNERS[cmd] || !RUNNERS[cmd][subCmd]) {
    process.stderr.write(`Unknown cmd ${cmd}, sub cmd ${subCmd}`)
    process.exit(1)
}
let runner = RUNNERS[cmd][subCmd];

(async () => {
    await runner(argv);
})().catch(e => {
    process.stderr.write(`${e.toString()}\n`)
    process.exit(1)
});
