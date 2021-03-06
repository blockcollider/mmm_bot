#!/bin/bash

set -e

action=$1
if [[ "$action" == "start" ]]
then
    webserver_container="mmm_webserver_container"

    cid=$(docker ps -q -f status=running -f name=^/${webserver_container}$)
    if [ "${cid}" ]; then
       echo "[Warn] Webserver is already running"
       docker logs ${webserver_container} | grep -A 5 'Please '
       exit 0
    fi

    image="blockcollider/mmm_bot:latest"
    if [[ "$(docker images -q $image > /dev/null)" != "" ]]; then
      echo "Remove stale docker image"
      docker rmi  $image > /dev/null 2>&1
    fi

    # remove any non running webserver container
    docker-compose down > /dev/null 2>&1 || true

    echo "[MMM_BOT] Building images (may take several minutes...)"
    docker-compose up --build --no-start > /dev/null 2>&1

    echo "[MMM_BOT] Refreshing the docker container"
    docker-compose start webserver > /dev/null

    echo "[MMM_BOT] Starting webserver"
    sleep 12 # ensure webserver is up and running
    docker logs ${webserver_container} | grep -A 5 'Please '
elif [[ "$action" == "stop" ]]
then
    docker-compose down
elif [[ "$action" == "restart" ]]
then
    ./mmm_bot.sh stop
    ./mmm_bot.sh start
else
    echo 'Usage: '
    echo '   ./mmm_bot.sh start '
    echo '      --> Start the webserver'
    echo '   ./mmm_bot.sh stop'
    echo '      --> Stop the webserver and mmm_bot'
fi
