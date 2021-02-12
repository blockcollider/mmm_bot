#!/bin/bash

# used inside docker

# trap ctrl-c and call ctrl_c()
trap ctrl_c INT

function ctrl_c() {
    echo "** Trapped CTRL-C"
    exit 0
}

cd "$(dirname "$0")"
# cd to the root
cd ..

poetry run alembic upgrade head > /dev/null 2>&1

while true
do
    REGISTER_TIMEOUT=true poetry run python mmm_bot.py
    echo "[xxxxxxxxxxxxx] Exit from mmm_bot.py, with exit code", $?
done
