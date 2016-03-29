#!/bin/bash

#
# This script runs the son-mano-slm plugin related tests.
#
# It starts four Docker containers:
# - RabbitMQ
# - MongoDB
# - son-mano-pluginmanager/Dockerfile
# - plugin/son-mano-service-lifecycle-management/Dockerfile
#
# It triggers the unittest execution in plugin/son-mano-service-lifecycle-management
#

# setup cleanup mechanism
trap "docker kill test.broker; docker kill test.mongo; docker kill test.pluginmanager; docker rm test.broker; docker rm test.mongo; docker rm test.pluginmanager; docker rm test.slm" INT TERM EXIT

#  always abort if an error occurs
set -e

echo "test_plugin-son-mano-slm.sh"
# build Docker images
docker build -t test.pluginmanager -f son-mano-pluginmanager/Dockerfile .
docker build -t test.slm -f plugins/son-mano-service-lifecycle-management/Dockerfile .

# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mongo mongo
# wait a bit for broker startup
sleep 10
# spin up the plugin manager
docker run -d --link test.broker:broker --link test.mongo:mongo --name test.pluginmanager test.pluginmanager
# wait a bit for manager startup
sleep 3
# spin up slm container and run py.test
docker run --link test.broker:broker --name test.slm test.slm py.test -v


echo "done."