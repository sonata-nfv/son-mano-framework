#!/bin/bash

set -e
set -x

echo "Run unittests placement executive"

# spin up placement executive container and run py.test
docker run --name test.mano.placementexecutive --net=son-mano-unittests --network-alias=test.mano.placementexecutive  \
-e broker_host=amqp://guest:guest@broker:5672/%2F \
-e sm_broker_host=amqp://specific-management:sonata@broker:5672 -e broker_man_host=http://broker:15672 \
registry.sonata-nfv.eu:5000/placementexecutive py.test -v

echo "placement executive unittests finised"

#clean-up
docker rm -fv test.manao.placementexecutive

# abort of tests failed
if [ $? -ne 0 ]; then exit 1; fi;

