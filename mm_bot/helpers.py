import os
import decimal

def decimal_to_str(num: decimal.Decimal, precision=80):
    return '{0:.{prec}f}'.format(num, prec=precision).rstrip('0')

LOGS_FILE_PATTERN = './logs/money_machine.log-'
CONFIG_DIR = os.environ.get('CONFIG_DIR', '/tmp/').rstrip('/')

def get_config_path(strategy):
    config_path = f'{CONFIG_DIR}/{strategy}.yaml'
    return config_path


def config_updated_lock_file(strategy):
    config_path = f'{CONFIG_DIR}/{strategy}.yaml.updated'
    return config_path

def signal_config_reloaded(strategy):
    config_path = config_updated_lock_file(strategy)
    os.system(f'touch {config_path}')

def is_config_reloaded(strategy):
    config_path = config_updated_lock_file(strategy)
    return os.path.isfile(config_path)

def refresh_reloaded_config_done(strategy):
    config_path = config_updated_lock_file(strategy)
    os.system(f'rm {config_path}')
