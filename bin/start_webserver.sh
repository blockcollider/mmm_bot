#!/bin/bash

# used inside docker

# trap ctrl-c and call ctrl_c()
trap ctrl_c INT

function ctrl_c() {
    echo "** Trapped CTRL-C"
    exit 0
}

cd "$(dirname "$0")"

# to root
cd ..

# always ensure db schema is up to date
poetry run alembic upgrade head > /dev/null 2>&1

poetry run python -u server.py
