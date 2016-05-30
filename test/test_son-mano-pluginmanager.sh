#!/bin/bash

#
# This script runs the son-mano-slm plugin related tests.
#
# It starts three Docker containers:
# - RabbitMQ
# - MongoDB
# - son-mano-pluginmanager/Dockerfile
#
# It triggers the unittest execution in son-mano-pluginmanager
#

# setup cleanup mechanism
trap "set +e; docker rm -fv test.broker; docker rm -fv test.mongo; docker rm -fv test.pluginmanager" INT TERM EXIT

# ensure cleanup
set +e
docker rm -fv test.broker
docker rm -fv test.mongo
docker rm -fv test.pluginmanager

#  always abort if an error occurs
set -e

echo "test_son-mano-pluginmanager.sh"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mongo mongo
# wait a bit for broker startup
while ! nc -z localhost 5672; do
sleep 1 && echo -n .; # waiting for rabbitmq
done;
# spin up the plugin manager and run tests
docker run --link test.broker:broker --link test.mongo:mongo --name test.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager py.test -v


echo "done."