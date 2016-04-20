#!/usr/bin/env bash

#
# This script triggers all test entrypoints located in test/.
# Using this, tests are called in the same way like done by Jenkins.
# You should always execute this before creating a PR.
#
set -x
set -e

# We have to build the containers locally (done by Jenkins job in CI)
docker build -t registry.sonata-nfv.eu:5000/sonmanobase -f son-mano-base/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/pluginmanager -f son-mano-pluginmanager/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/exampleplugin -f plugins/son-mano-example-plugin-1/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/servicelifecyclemanagement -f plugins/son-mano-service-lifecycle-management/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/functionlifecyclemanagement -f plugins/son-mano-function-lifecycle-management/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/placementexecutive -f plugins/son-mano-placement/Dockerfile .

for i in `find . -name test_*.sh -type f`; do $i; if [ $? -ne 0 ]; then exit 1; fi; done