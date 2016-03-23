#!/bin/bash

#
# This script runs the son-mano-slm plugin related tests.
#
# It starts two Docker containers:
# - son-mano-broker/Dockerfile
# - son-mano-pluginmanager/Dockerfile
#
# It triggers the unittest execution in son-mano-pluginmanager
#

# setup cleanup mechanism
trap "docker kill test.broker; docker rm test.broker; docker rm test.pluginmanager" INT TERM EXIT

#  always abort if an error occurs
set -e

echo "test_son-mano-pluginmanager.sh"
# build Docker images
docker build -t test.broker -f son-mano-broker/Dockerfile .
docker build -t test.pluginmanager -f son-mano-pluginmanager/Dockerfile .


# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker test.broker
# wait a bit for broker startup
sleep 10
# spin up the plugin manager and run tests
docker run --link test.broker:broker --name test.pluginmanager test.pluginmanager py.test -v


echo "done."