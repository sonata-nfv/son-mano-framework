#!/bin/sh

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


trap "set +e; docker rm -fv test.broker; docker rm -fv test.mongo; docker rm -fv test.pluginmanager; docker rm -fv test.placementexecutive; " INT TERM EXIT

# ensure cleanup
set +e
docker rm -fv test.broker
docker rm -fv test.mongo
docker rm -fv test.pluginmanager
docker rm -fv test.placementexecutive

#  always abort if an error occurs
set -e

echo "test_son-mano-placement-executive.sh"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# wait a bit for broker startup
while ! nc -z localhost 5672; do
sleep 1 && echo -n .; # waiting for rabbitmq
done;
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mongo mongo
# wait a bit for db startup
while ! nc -z localhost 27017; do
sleep 1 && echo -n .; # waiting for mongo
done;
sleep 3
# spin up the plugin manager
docker run -d --link test.broker:broker --link test.mongo:mongo --name test.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager
# wait a bit for manager startup
sleep 3
# spin up placement executive container and run py.test
docker run --link test.broker:broker --name test.placementexecutive registry.sonata-nfv.eu:5000/scalingexecutive py.test -v

echo "done."