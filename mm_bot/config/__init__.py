import os
import pathlib

import everett.manager
import everett.ext.yamlfile

default_config_yaml = './config.yaml'

if os.environ.get('MMBC_CONFIG_FILE') is not None:
    config_yaml = os.environ.get('MMBC_CONFIG_FILE')
    print(f'Using config file: {config_yaml}')
else:
    config_yaml = default_config_yaml

# TODO do not have a default yaml file - just add ConfigYamlEnv if user provides it
manager = everett.manager.ConfigManager([
    everett.manager.ConfigOSEnv(),
    everett.ext.yamlfile.ConfigYamlEnv([config_yaml]),
    everett.manager.ConfigDictEnv({
        # db file is relative to the working dir, relative path is the path 'raw' after the three initial slashses
        'MMBC_DATABASE_URL': 'sqlite+pysqlite:///db/database.sqlite',
        'MMBC_SLEEP': 1,
        'MMBC_DRY_RUN': 'true',
        'MMBC_MIN_PROFITABILITY_RATE': '0.001',
        'MMBC_MAX_QTY_PER_ORDER': '0.007',
        'MMBC_MAX_OPEN_ORDERS': 3,
        'MMBC_MAX_OPEN_TAKER_ORDERS': 2,
        'MMBC_SHOULD_CANCEL_ORDER': 'false', # a very small number to indicate no cancel
        'MMBC_CANCEL_ORDER_THRESHOLD': '0.00000001', # a very small number to indicate no cancel
        'MMBC_EXCHANGE_BINANCE_LOOP_DELAY': 1,
        'MMBC_EXCHANGE_BORDERLESS_LOOP_DELAY': 1,
        'MMBC_EXCHANGE_BORDERLESS_PARTIAL_ORDER': 'false',
        'MMBC_EXCHANGE_BORDERLESS_MAX_NRG_FEE_PER_TX': 20,
        'MMBC_EXCHANGE_BORDERLESS_MAX_NRG_FEE_PER_DAY': 100,
        'MMBC_EXCHANGE_BORDERLESS_MAX_NRG_ACCEPT_DAILY': 30000,
        'MMBC_EXCHANGE_BORDERLESS_DEPOSIT_LENGTH': 100,
        'MMBC_EXCHANGE_BORDERLESS_SETTLEMENT_WINDOW_LENGTH': 150,
        'MMBC_EXCHANGE_DESTINATION_MINER_SCOOKIE': 'testCookie123',
        })
    ])
config = manager.with_namespace('mmbc')

__all__ = ['config']
