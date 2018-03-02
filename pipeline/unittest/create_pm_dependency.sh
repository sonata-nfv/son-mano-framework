#!/bin/bash

set -e
set -x

echo "Run Plugin Manager, to be used by next unittests"

# execute the container
docker run -d --name test.mano.pluginmanager --net=son-mano-unittests \
--network-alias=pluginmanager --name test.mano.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager

sleep 10

echo "Plugin Manager unittests finised"