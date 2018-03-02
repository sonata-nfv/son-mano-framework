#!/bin/bash

set -e
set -x

echo "Run unittests Service Lifecycle Manager"

# spin up slm container and run py.test
docker run --name test.mano.slm --net=son-mano-unittests --network-alias=servicelifecyclemanagement \
registry.sonata-nfv.eu:5000/servicelifecyclemanagement py.test -v

echo "Service Lifecycle Manager unittests finised"

#clean-up
docker rm -fv test.mano.slm

# abort of tests failed
if [ $? -ne 0 ]; then exit 1; fi;
