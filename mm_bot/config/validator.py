from mm_bot.config import config
from decimal import Decimal

class InvalidParam(Exception):
    pass

STRATEGY_NAME_KEY = 'strategy_name'

REQUIRED_PARAMS = [
    ('dry_run', bool),
    ('should_cancel_order', bool),
    ('cancel_order_threshold', Decimal),
    ('exchange_destination_miner_address', str),
    ('exchange_destination_miner_scookie', str),
    ('exchange_destination_nrg_private_key', str),
    ('exchange_destination_nrg_public_key', str),
    ('max_open_orders', int),
    ('max_qty_per_order', Decimal),
    ('min_profitability_rate', Decimal),
    ('exchange_source_api_key', str),
    ('exchange_source_api_secret', str),
    ('wallet_base_currency_name', str),
    ('wallet_base_currency_private_key', str),
    ('wallet_base_currency_wallet', str),
    ('wallet_counter_currency_name', str),
    ('wallet_counter_currency_private_key', str),
    ('wallet_counter_currency_wallet', str),
]

def validate_cross_exchange_configs():
    invalid_params = []
    for param, parser in REQUIRED_PARAMS:
        val = config(param, parser=parser)
        if val == 'fillme':
            invalid_params.append(param)

    if len(invalid_params) > 0:
        raise InvalidParam('Please fill these values: \n\n' + '\n'.join(invalid_params))


def validate():
    strategy_name = config(STRATEGY_NAME_KEY, parser=str)
    if strategy_name == 'cross_market':
        validate_cross_exchange_configs()

