#!/bin/bash

#
# This script runs the son-mano-base related tests.
#
# It starts two Docker containers:
# - RabbitMQ
# - son-mano-base/Dockerfile
#
# It triggers the unittest execution in son-mano-base.
#

# setup cleanup mechanism
trap "set +e; docker rm -fv test.broker; docker rm -fv test.sonmanobase" INT TERM EXIT

# ensure cleanup
set +e
docker rm -fv test.broker
docker rm -fv test.mongo
docker rm -fv test.pluginmanager
docker rm -fv test.sonmanobase

#  always abort if an error occurs
set -e

echo "test_son-mano-base.sh"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# wait a bit for broker startup
while ! nc -z localhost 5672; do
sleep 1 && echo -n .; # waiting for rabbitmq
done;
sleep 3
# spin up the son-mano-base test container and execute its unittests
docker run --link test.broker:broker -v '/var/run/docker.sock:/var/run/docker.sock' --name test.sonmanobase registry.sonata-nfv.eu:5000/sonmanobase py.test -v

echo "done."
