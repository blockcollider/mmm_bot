import collections
import json
import os
import requests
import shutil
import uuid
import yaml
import time
import logging
import subprocess
import base64


from datetime import datetime, timezone
from functools import wraps
from glob import glob

import binance
from binance.client import Client as BinanceClient
from binance.exceptions import BinanceAPIException, BinanceWithdrawException

from sanic import Blueprint, Sanic
from sanic.response import json as json_response
from sanic.response import html, redirect, file_stream
from sanic.exceptions import NotFound

from sanic_session import Session, InMemorySessionInterface

from jinja2 import Environment, PackageLoader


app = Sanic(__name__)
app.static('/static', './server/static')

from sanic.log import logger
logger.setLevel(logging.WARN)


session = Session(app, interface=InMemorySessionInterface())

# we a very simple way for auth
app.token = uuid.uuid4().hex

jinja_env = Environment(loader=PackageLoader('server', 'server/templates'))

from mm_bot.config import config
from mm_bot.config.validator import REQUIRED_PARAMS, STRATEGY_NAME_KEY
from mm_bot.helpers import get_config_path, signal_config_reloaded, LOGS_FILE_PATTERN
from mm_bot.model.repository import OrderRepository

url = config('database_url', parser=str)
order_repository = OrderRepository(url)

def get_borderless_balance(endpoint, public_key, scookie):
    url = f"{endpoint}/rpc"

    payload = {"id":1,"jsonrpc":"2.0","method":"getBalance","params":[public_key]}
    headers = {'Content-Type': 'application/json'}
    if scookie:
        token = ':' + scookie
        token = base64.b64encode(token.encode('ascii')).decode('ascii')
        headers['authorization'] = f"Basic {token}"
    try:
        response = requests.request("POST", url, headers=headers, json=payload)
        if response.ok:
            return response.json()
        else:
            return False
    except Exception as e:
        print('error', e)
        return False

def validate_binance_key(api_key, api_secret):
    try:
        client = binance.Client(api_key, api_secret)

        account = client.get_account()

        # test order creation
        client.create_test_order(
            symbol='ETHBTC',
            side=binance.AsyncClient.SIDE_SELL,
            type=binance.AsyncClient.ORDER_TYPE_LIMIT,
            timeInForce=binance.AsyncClient.TIME_IN_FORCE_GTC,
            quantity=1,
            price=0.034175,
        )

        asset_id = 'BTC'
        to_addr = client.get_deposit_address(asset=asset_id)['address']
        amount = '0.0001' # this is an invalid amount to withdraw, we use this to test
        # test withdraw
        result = client.withdraw(
                asset=asset_id,
                address=to_addr,
                amount=amount)
    except BinanceAPIException as e:
        return False, f'Failed to validate your binance keys based on the keys, error: {str(e)}'
    except BinanceWithdrawException as e:
        return True, ''
    except KeyError as e: # a bug, in python-binance
        return False, f'Your key cannot withdraw assets, be sure to enable Withdrawals of your API key and run the bot in your whitelisted IPs'

    return True, ''

def get_token(request):
    token = request.args.get('token')

    if token is None:
        token = request.ctx.session.get('token')

    if token is None:
        return False

    return token

def authorized():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            # run some method that checks the request
            # for the client's authorization status
            token = get_token(request)

            if token == app.token:
                request.ctx.session['token'] = token
                response = await f(request, *args, **kwargs)
                return response
            else:
                return redirect('/login')

        return decorated_function
    return decorator

@app.route('/login', methods=['POST', 'GET'])
def login(request):
    if get_token(request) == app.token:
        return redirect('/')

    if request.method == 'GET':
        template = jinja_env.get_template('login.html')
        html_content = template.render()

        return html(html_content)

    req = request.form
    token = req.get('token')
    if token == app.token:
        request.ctx.session['token'] = token
        return redirect('/')
    else:
        return redirect('/login')


@app.route('/')
@authorized()
async def load_config(request):
    strategy = 'cross_market'

    config_path = get_config_path(strategy)
    params = collections.defaultdict(lambda: '')
    if os.path.isfile(config_path):
        with open(config_path, 'r') as f:
            params = yaml.load(f, Loader=yaml.FullLoader)['mmbc']
    else:
        default_keys = [
            'cancel_order_threshold',
            'max_open_orders',
            'max_open_taker_orders',
            'max_qty_per_order',
            'min_profitability_rate',
        ]
        for key in default_keys:
            params[key] = config(key, parser=str)

    template = jinja_env.get_template(f'{strategy}.html')
    html_content = template.render(params=params)

    return html(html_content)

@app.route('/monitor', methods=["GET"])
@authorized()
async def get_monitor_page(request):
    template = jinja_env.get_template('monitor.html')
    html_content = template.render()

    return html(html_content)


@app.route('/bot_action', methods=["POST"])
@authorized()
async def perform_action(request):
    action = request.json.get('action', '').strip().lower()

    mmm_bot_container_name = 'mmm_bot_container'
    if action == 'start':
        check_running_cmd = f"docker ps -q -f status=running -f name=^/{mmm_bot_container_name}$"
        output = subprocess.check_output(check_running_cmd, shell=True).decode('utf8').strip()
        if output:
            return json_response({'status': 'ok', 'container_id': output})

        cmd = f"docker start {mmm_bot_container_name}"
        subprocess.check_call(cmd, shell=True)

        output = subprocess.check_output(check_running_cmd, shell=True).decode('utf8').strip()
        return json_response({'status': 'ok', 'container_id': output})
    elif action == 'stop':
        cmd = f'docker stop {mmm_bot_container_name}'
        subprocess.check_call(cmd, shell=True)

        return json_response({'status': 'ok', 'container_id': ''})
    else:
        return json_response({'status': 'ok', 'container_id': ''})

@app.route('/bot_heartbeat', methods=["GET"])
@authorized()
async def get_bot_heartbeat(request):
    heartbeat_file = os.environ.get('HEARTBEAT_FILE', None)
    if heartbeat_file is None:
        return json_response({'health': False, 'reason': 'Bot not initialized', 'heartbeat_at_utc': None, 'error': None})

    if not os.path.isfile(heartbeat_file):
        return json_response({'health': False, 'reason': 'Bot not initialized', 'heartbeat_at_utc': None, 'error': None})

    reason = ''
    health = True
    with open(heartbeat_file, 'r') as f:
        data = f.read().strip()
        utc, epoch, error = data.split(',', 2)

        stale = int(time.time()) - int(epoch)
        error = error.replace('"', '')
        if error:
            health = False
            reason = f'Heartbeat with error: {error}'
        elif stale > 2 * 60:
            health = False
            reason = f'Has not performed heartbeat since {round(stale / 60.0, 2)} minute ago'

    return json_response({'health': health, 'reason': reason, 'heartbeat_at_utc': utc, 'error': error})


@app.route('/logs', methods=["GET"])
@authorized()
async def get_logs(request):
    log_files = LOGS_FILE_PATTERN + '*'
    all_log_files = sorted(list(glob(log_files)), reverse=True)

    logs = []
    for log in all_log_files:
        timestamp = log.split('-')[1]
        url_path = timestamp
        if '.' in timestamp: # rotated filename
            timestamp = timestamp.split('.')[0]

        logs.append((datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat(), log, url_path))

    template = jinja_env.get_template('logs.html')
    html_content = template.render(logs=logs)

    return html(html_content)

@app.route('/logs/<filename>', methods=["GET"])
@authorized()
async def download_log(request, filename):
    logfile_path = LOGS_FILE_PATTERN + filename

    return await file_stream(logfile_path)

@app.route('/orders', methods=["GET"])
@authorized()
async def get_orders(request):
    maker_orders = await order_repository.get_all_orders('maker')
    taker_orders = await order_repository.get_all_orders('taker')

    maker_id_to_taker_order = {t.maker_order_id: t for t in taker_orders}

    sorted_maker_orders = sorted(maker_orders, key=lambda o: o.id, reverse=True)

    maker_taker_order_pairs_by_currency = {}
    for maker_order in sorted_maker_orders:
        taker = maker_id_to_taker_order.get(maker_order.id, None)
        if taker:
            taker = taker.as_object()
        pair = {
            "maker": maker_order.as_object(),
            "taker": taker,
        }
        currency = maker_order.currency
        if currency not in maker_taker_order_pairs_by_currency:
            maker_taker_order_pairs_by_currency[currency] = []
        maker_taker_order_pairs_by_currency[currency].append(pair)

    template = jinja_env.get_template('orders.html')
    html_content = template.render(maker_taker_order_pairs_by_currency=maker_taker_order_pairs_by_currency)

    return html(html_content)

@app.route('/test_binance_keys', methods=["GET"])
@authorized()
async def test_bc_params(request):
    api_key = request.args.get('exchange_source_api_key')
    api_secret = request.args.get('exchange_source_api_secret')
    res, reason = validate_binance_key(api_key, api_secret)
    return json_response({'is_valid': res, 'reason': reason})

@app.route('/test_bc_params', methods=["GET"])
@authorized()
async def test_bc_params(request):
    miner_address = request.args.get('exchange_destination_miner_address')
    scookie = request.args.get('exchange_destination_miner_scookie')
    public_key = request.args.get('exchange_destination_nrg_public_key')
    res = get_borderless_balance(miner_address, public_key, scookie)
    return json_response({'is_valid': res})

@app.route('/exchange_wallet', methods=["POST"])
@authorized()
async def exchange_wallet(request):
    exchange_name = request.json.get('exchange_name')

    api_key = request.json.get('api_key')
    api_secret = request.json.get('api_secret')
    assets = request.json.get('assets')

    binance_client = BinanceClient(api_key, api_secret)

    res = {}
    for asset in assets:
        binance_asset = asset
        if asset == 'WAV':
            binance_asset = 'WAVES'
        deposit_address = binance_client.get_deposit_address(asset=binance_asset)
        res[asset] = deposit_address['address']

    return json_response(res)

@app.route('/save_config', methods=["POST"])
@authorized()
async def save_config(request):
    req = request.form

    strategy = req.get(STRATEGY_NAME_KEY)

    assert strategy is not None

    keys = list(map(lambda p: p[0], REQUIRED_PARAMS))
    keys.append(STRATEGY_NAME_KEY)

    config_lines = ['mmbc:']
    for key in keys:
        value = req.get(key)
        line = f'  {key}: "{value}"' # manually construct the format, as everrett requires quotes in the value
        config_lines.append(line)


    config_path = get_config_path(strategy)
    print('Saving to ', config_path)

    with open(config_path, 'w') as f:
        f.write('\n'.join(config_lines))

    signal_config_reloaded(strategy)
    return redirect('/')


def get_my_public_ip():
    try:
        res = requests.get("https://httpbin.org/ip")
        data = res.json()
        return data['origin']
    except:
        return None

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 38080))
    ip = get_my_public_ip()

    print(f'\n\n[MMM_BOT] Please copy and paste the URL to config your bot:')
    print(f'          http://localhost:{port}?token={app.token}\n')
    if ip is not None:
        print(f'          OR \n')
        print(f'          http://{ip}:{port}?token={app.token}\n\n')

    if os.environ.get('APP_ENV', 'dev') != 'prod':
        debug = True
    else:
        debug = False
    app.run(debug=debug, port=port, host="0.0.0.0", access_log=False, worker=1)
