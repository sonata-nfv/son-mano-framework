#!/bin/bash

#
# This script runs the son-mano-slm plugin related tests.
#
# It starts two Docker containers:
# - son-mano-broker/Dockerfile
# - son-mano-pluginmanager/Dockerfile
# - plugin/son-mano-service-lifecycle-management/Dockerfile
#
# It triggers the unittest execution in plugin/son-mano-service-lifecycle-management
#

# setup cleanup mechanism
trap "docker kill test.broker; docker rm test.broker; docker rm test.slm" INT TERM EXIT

#  always abort if an error occurs
set -e

echo "test_plugin-son-mano-slm.sh"
# build Docker images
docker build -t test.broker -f son-mano-broker/Dockerfile .
docker build -t test.slm -f plugins/son-mano-service-lifecycle-management/Dockerfile .

# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker test.broker
# wait a bit for broker startup
sleep 10
# spin up slm container and run py.test
docker run --link test.broker:broker --name test.slm test.slm py.test -v


echo "done."
