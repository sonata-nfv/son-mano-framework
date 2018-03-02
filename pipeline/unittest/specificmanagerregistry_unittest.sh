#!/bin/bash

set -e
set -x

echo "Run unittests Specific Manager Registry"

# spin up smr container and run py.test
docker run --name test.mano.smr --net=son-mano-unittests --network-alias==specificmanagerregistry \
-v '/var/run/docker.sock:/var/run/docker.sock' \
-e network_id=son-mano-unittests  -e broker_man_host=http://broker:15672 \
-e broker_host=amqp://guest:guest@broker:5672/%2F \
-e sm_broker_host=amqp://specific-management:sonata@broker:5672 \
registry.sonata-nfv.eu:5000/specificmanagerregistry py.test -v

echo "Specific Manager Registry unittests finised"

#clean-up
#docker rm -fv $(docker ps -a -f "name=sonssm")
#docker rm -fv $(docker ps -a -f "name=sonfsm")
docker rm -fv test.mano.smr

# abort of tests failed
if [ $? -ne 0 ]; then exit 1; fi;

