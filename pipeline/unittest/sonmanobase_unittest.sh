#!/bin/bash

set -e
set -x

echo "Run unittests sonmanobase"
# spin up the son-mano-base test container and execute its unittests
docker run --name test.mano.sonmanobase --net=son-mano-unittests --network-alias=sonmanobase \
-v '/var/run/docker.sock:/var/run/docker.sock' \
registry.sonata-nfv.eu:5000/sonmanobase py.test -v

echo "sonmanobase unittests finised"

#clean-up
docker rm -fv test.mano.sonmanobase

# abort of tests failed
if [ $? -ne 0 ]; then exit 1; fi;

