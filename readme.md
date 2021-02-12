# Multi-Market Maker bot

There are two ways to run the bot

## Option 1: Run the bot with docker (recommended way)

You can install the docker from [link](https://docs.docker.com/get-docker/) and
docker-compose (https://docs.docker.com/compose/install/)

Step 1: Clone the git repo: `git clone https://github.com/blockcollider/market_maker.git`

Step 2: `cd` into the folder: `cd market_maker` and run `./mmm_bot.sh start` to config your strategy.

**Note**: The webserver is authorized by an ephemeral token generated on the server bootstrap. If you forget the token, you can get it via running this command: `./mmm_bot.sh start`, which gives you the url to access your webserver

`./mmm_bot.sh` will show you how to use the cli.

## Option 2: Run with source code

### Environment / OS setup

You need to follow these steps only when you choose to run the bot on bare operating system.
For running using Docker you can fast forward to "run using docker" section

### Prerequisites

- python >= 3.7
- nodejs >= 10.16
- yarn
- poetry

### Ubuntu 18.04 LTS setup

Ubuntu 18.04 LTS has both 2 and 3 python versions of python present. We want to use python 3 for setup and running of MM bot but we need 3.7 version

run:

- `apt install python3.7 python3.7-dev python3-distutils python3.7-venv` for installing latest python 3.7 and poetry's needed dependencies
- `curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3.7` (note the 3.7 at the end)
- `sed -i 's/python/python3.7/' $HOME/.poetry/bin/poetry` to use ubuntu's custom python3 environment

### MacOS

TBD

### Before First Run

#### Install Dependencies

```bash
poetry install
cd mm_bot/exchange/maker && yarn && cd -
```

#### Prepare Database Environment

- MMM bot uses sqlite database
- default database location is `db/database.sqlite`, you can change `MMBC_DATABASE_URL` to any location
    - mind that `MMBC_DATABASE_URL` accepts full [SQLAlchemy connection string](https://docs.sqlalchemy.org/en/13/core/engines.html#sqlite), default is `sqlite+pysqlite:///db/database.sqlite`
- run `poetry run alembic upgrade head` to create sqlite DB file and apply all migrations
-

### Run test

you can run `poetry run pytest` in the root directory, all tests should pass before running

### Run the web ui to config the parameters

```bash
poetry run python server.py
```

### Run the bot

```
poetry run python mmm_bot.py
```


## Move liquidity from taker exchanges to maker exchange

It means there is more liquidity in the taker exchanges with smaller bid-ask spread.

There are two types of orders: buy order and sell order

1. Buy order. Bot creates a limit buy order on the maker exchange. Once this
   order is filled, it immediately creates an opposite sell order in the taker exchange.
   This requires the `Price(bid, taker exchange) > Price(bid, maker exchange)`
   when opening a buy order in the maker exchange

2. Sell order. Bot creates a limit sell order in the maker exchange. Once this
   order is filled, it immediately creates an opposite buy order in the taker exchange.
   This requires the `Price(ask, taker exchange) < Price(ask, maker exchange)`
   when opening a buy order in the maker exchange


## FAQ

### Are my private keys and API keys secure?

Since the MMM Bot is a local client, your private keys and API keys are as secure as the computer you use.
The keys are only used to sign authorized instructions locally on the local machine, and only signed/authorized transactions are sent out from the client.
Always use caution and make sure the computer you are running MMM Bot on is safe, secure, and free from unauthorized access.
