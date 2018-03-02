#!/bin/bash

set -e
set -x

echo "Run unittests Plugin Manager"

# execute the container in test mode
docker run --name test.mano.pluginmanager --net=son-mano-unittests \
--network-alias=pluginmanager --name test.mano.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager py.test -v

echo "Plugin Manager unittests finised"

#clean-up
docker rm -fv test.mano.pluginmanager

# abort of tests failed
if [ $? -ne 0 ]; then exit 1; fi;
