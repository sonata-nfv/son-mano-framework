#!/bin/bash

set -e
set -x

echo "Clean up leftovers from SONATA jobs"

docker rm -fv $(docker ps -a -f "network=test.sonata-plugins") || true

echo "Create docker network MANO unittests"

# spin up a docker network
docker network create son-mano-unittests

echo "Run a rabbitmq broker container"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 -p 15672:15672 --name test.mano.broker --net=son-mano-unittests --network-alias=broker rabbitmq:3-management

# wait a bit for broker startup
while [ true ]
do
	export vhosts=`curl http://localhost:15672/api/vhosts/ -u guest:guest | grep "name"`
    if [ -z $vhosts ]
    then
            echo "broker has not started yet"
    else
            echo "broker has started"
            break
    fi
    sleep 1
done

echo "Run a Mongo DB container"
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mano.mongo --net=son-mano-unittests --network-alias=mongo  mongo
# wait a bit for db startup
while ! nc -z localhost 27017; do
sleep 1 && echo -n .; # waiting for mongo
done;

echo "Dependencies setup completed"
