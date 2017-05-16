#!/usr/bin/env bash

# Copyright (c) 2015 SONATA-NFV
# ALL RIGHTS RESERVED.
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

#
# This script triggers all test entrypoints located in test/.
# Using this, tests are called in the same way like done by Jenkins.
# You should always execute this before creating a PR.
#
set -x
set -e

# We have to build the containers locally (done by Jenkins job in CI)
docker build -t registry.sonata-nfv.eu:5000/sonmanobase -f son-mano-base/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/pluginmanager \
-f son-mano-pluginmanager/Dockerfile .
#docker build -t registry.sonata-nfv.eu:5000/exampleplugin -f plugins/son-mano-example-plugin-1/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/testplugin \
-f plugins/son-mano-test-plugin/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/servicelifecyclemanagement \
-f plugins/son-mano-service-lifecycle-management/Dockerfile .
#docker build -t registry.sonata-nfv.eu:5000/functionlifecyclemanagement \
# -f plugins/son-mano-function-lifecycle-management/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/placementexecutive \
-f plugins/son-mano-placement-executive/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/scalingexecutive \
-f plugins/son-mano-scaling-executive/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/specificmanagerregistry \
-f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .

for i in `find . -name test_*.sh -type f`; do $i; if [ $? -ne 0 ]; then exit 1; fi; done
