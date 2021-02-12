import asyncio
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from decimal import Decimal

import aiopubsub
import everett

from mm_bot.config import config
from mm_bot.config import validator
from mm_bot.model import constants
from mm_bot.model.currency import CurrencyPair
from mm_bot.model.repository import OrderRepository
from mm_bot.strategy.cross_market import CrossMarketStrategy
from mm_bot.exchange.maker.borderless import Borderless
from mm_bot.exchange.taker.binance import Binance
from mm_bot import helpers

LOGLEVEL = logging.getLevelName(os.environ.get('MMBC_LOGLEVEL', 'INFO').upper())
root_logger = logging.getLogger()
root_logger.setLevel(LOGLEVEL)
# 20 MB
fh = logging.handlers.RotatingFileHandler(f'{helpers.LOGS_FILE_PATTERN}{int(time.time())}', mode='a', maxBytes=20971520, backupCount=50)
fh.setLevel(LOGLEVEL)
ch = logging.StreamHandler()
ch.setLevel(LOGLEVEL)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
ch.setFormatter(formatter)
root_logger.addHandler(fh)
root_logger.addHandler(ch)

logging.getLogger("everett").setLevel(logging.WARNING)

LOGGER = logging.getLogger('market_maker_bot.main')

ENGINE_TIMEOUT_VALUE = 8 * 60 * 60 # in seconds
async def timeout_to_reclaim_memory():
    """
    timeout the process to reclain memory and avoid OOM error
    """
    timeout_value = int(os.environ.get("ENGINE_TIMEOUT_VALUE", ENGINE_TIMEOUT_VALUE))
    LOGGER.info('Register timeout with value: %s', timeout_value)
    await asyncio.sleep(timeout_value)

def exit_after_callback(fur):
    raise SystemExit(0)

def register_timeout(loop):
    future = loop.create_task(timeout_to_reclaim_memory())
    future.add_done_callback(exit_after_callback)
    return future

async def check_if_config_reloaded(strategy_name):
    while True:
        if helpers.is_config_reloaded(strategy_name):
            LOGGER.warning(f'Config of {strategy_name} was updated. Reloading MMM bot')
            helpers.refresh_reloaded_config_done(strategy_name)
            raise SystemExit(0)

        await asyncio.sleep(1)

def register_checking_config(loop, strategy_name):
    LOGGER.info('Register checking reloaded config for strategy: %s', strategy_name)
    task = loop.create_task(check_if_config_reloaded(strategy_name))
    return task

def main(loop: asyncio.AbstractEventLoop) -> None:
    strategy_name = config('strategy_name', parser=str)
    LOGGER.info(f'Start with strategy: {strategy_name}')

    check_config_task = None
    if os.environ.get('REGISTER_CHECK_CONFIG', 'false').lower() == 'true':
        check_config_task = register_checking_config(loop, strategy_name)

    timeout_task = None
    if os.environ.get('REGISTER_TIMEOUT', 'false').lower() == 'true':
        timeout_task = register_timeout(loop)

    try:
        strategy = None
        hub = aiopubsub.Hub()

        url = config('database_url', parser=str)
        order_repository = OrderRepository(url)

        base = config('wallet_base_currency_name', parser=lambda s: str(s).upper())
        if not constants.SupportedCurrency[base] in constants.SupportedCurrency:
            LOGGER.warning(f'Unsupported base: {base}')

        counter = config('wallet_counter_currency_name', parser=lambda s: str(s).upper())
        if not constants.SupportedCounterCurrency[counter] in constants.SupportedCounterCurrency:
            LOGGER.warning(f'Unsupported counter: {counter}')

        if base == counter:
            raise ValueError(f'base and counter has to be different, base: {base}, counter: {counter}')
        currency = CurrencyPair(base, counter)

        base_address = config('wallet_base_currency_wallet', parser=str)
        counter_address = config('wallet_counter_currency_wallet', parser=str)
        scookie = config('exchange_destination_miner_scookie', parser=str)
        borderless = Borderless(
                hub, currency,
                config('exchange_destination_miner_address', parser=str),
                scookie,
                config('exchange_destination_nrg_public_key', parser=str),
                config('exchange_destination_nrg_private_key', parser=str),
                base_address,
                counter_address
                )

        binance = Binance(
            hub, currency, config('exchange_binance_loop_delay', parser=int),
            config('exchange_source_api_key', parser=str),
            config('exchange_source_api_secret', parser=str)
        )

        strategy = CrossMarketStrategy(
                hub, order_repository, binance, borderless, currency,
                config('max_open_orders', parser=int),
                config('min_profitability_rate', parser=Decimal),
                config('max_qty_per_order', parser=Decimal),
                config('cancel_order_threshold', parser=Decimal),
                config('should_cancel_order', parser=bool),
                )
        strategy.start()
        loop.run_forever()
    except KeyboardInterrupt:
        LOGGER.debug('Interrupt received, stopping')
    except everett.ConfigurationMissingError as err:
        missing_key = f'{"_".join(err.namespace)}_{err.key}'
        LOGGER.warning(f'You have to set configuration key {missing_key.upper()}')
    except:
        LOGGER.exception('Exception in main loop')
    finally:
        if strategy is not None:
            loop.run_until_complete(strategy.stop())
        if timeout_task is not None and not timeout_task.done():
            timeout_task.cancel()

        if check_config_task is not None and not check_config_task.done():
            check_config_task.cancel()

        # find all futures/tasks still running and wait for them to finish
        pending_tasks = [
            task for task in asyncio.Task.all_tasks() if not task.done()
        ]
        LOGGER.info('Gathering all pending tasks: %s', pending_tasks)
        loop.run_until_complete(asyncio.gather(*pending_tasks))
        loop.stop()
        # loop.close()


def _check_nodejs_presence_and_version():
    # TODO test: result = subprocess.run(['/bin/bash', '-s', '-c',  'echo v8.12.8'], capture_output = True)
    result = subprocess.run(['/usr/bin/env', 'node', '--version'], capture_output = True)
    if result.returncode != 0:
        LOGGER.error('Could not find nodejs binary (using /usr/bin/env node --version)')
        sys.exit(1)

    raw_output = result.stdout.decode('ascii')
    try:
        version = raw_output.strip().split('v')[1]
        [major, minor, _] = version.split('.')

    except:
        LOGGER.error(f'Could not parse nodejs version from {raw_output}')
        sys.exit(1)

    if int(major) < 10 or int(minor) < 12:
        LOGGER.error(f'Nodejs version >= 10.12 is needed, got {major}.{minor}')
        sys.exit(1)


if __name__ == '__main__':
    validator.validate()

    _check_nodejs_presence_and_version()

    strategy_name = config('strategy_name', parser=str)
    if helpers.is_config_reloaded(strategy_name):
        helpers.refresh_reloaded_config_done(strategy_name)

    loop = asyncio.get_event_loop()
    main(loop)
