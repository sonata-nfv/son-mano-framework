#!/bin/bash

#
# This script runs the son-mano-base related tests.
#
# It starts two Docker containers:
# - RabbitMQ
# - son-mano-base/Dockerfile
#
# It triggers the unittest execution in son-mano-base/Dockerfile.
#

# setup cleanup mechanism
trap "docker kill test.broker; docker rm test.broker; docker rm test.sonmanobase" INT TERM EXIT

#  always abort if an error occurs
set -e

echo "test_son-mano-base.sh"
# build Docker images
#docker build -t test.sonmanobase -f son-mano-base/Dockerfile .
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# wait a bit for broker startup
sleep 10
# spin up the son-mano-base test container and execute its unittests
docker run --link test.broker:broker --name test.sonmanobase sonmanobase py.test -v

echo "done."
