#!/bin/bash

#
# This script runs the son-mano-base related tests.
#
# It starts two Docker containers:
# - son-mano-broker/Dockerfile
# - son-mano-base/test.Dockerfile
#
# It triggers the unittest execution in son-mano-base/test.Dockerfile.
#

# setup cleanup mechanism
trap "docker kill test.broker; docker rm test.broker; docker rm test.sonmanobase" INT TERM EXIT

#  always abort if an error occurs
set -e

echo "test_son-mano-base.sh"
cd ..;  # use root dir as working dir
# build Docker images
docker build -t test.broker -f son-mano-broker/Dockerfile .
docker build -t test.sonmanobase -f son-mano-base/test.Dockerfile .
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker test.broker
# wait a bit for broker startup
sleep 10
# spin up the son-mano-base test container and execute its unittests
docker run -it --link test.broker:broker --name test.sonmanobase test.sonmanobase

echo "done."
