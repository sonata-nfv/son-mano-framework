#!/bin/bash

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

# This script runs the son-mano-base related tests.
#
# It starts two Docker containers:
# - RabbitMQ
# - son-mano-base/Dockerfile
#
# It triggers the unittest execution in son-mano-base.
#

trap "set +e
# Show containers logs
docker logs test.broker
docker logs test.mongo
docker logs test.pluginmanager
docker logs test.sonmanobase
# Remove containers
docker rm -fv test.broker
docker rm -fv test.mongo
docker rm -fv test.pluginmanager
docker rm -fv test.sonmanobase" INT TERM EXIT
#docker network rm test.sonata-plugins" INT TERM EXIT

# ensure cleanup
set +e
if ! [[ "$(docker inspect -f {{.State.Running}} test.broker 2> /dev/null)" == "" ]]; then docker rm -fv test.broker ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.mongo 2> /dev/null)" == "" ]]; then docker rm -fv test.mongo ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.pluginmanager 2> /dev/null)" == "" ]]; then docker rm -fv test.pluginmanager ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.placementexecutive 2> /dev/null)" == "" ]]; then docker rm -fv test.placementexecutive ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.sonmanobase 2> /dev/null)" == "" ]]; then docker rm -fv test.sonmanobase ; fi
#docker rm -fv test.broker
#docker rm -fv test.mongo
#docker rm -fv test.pluginmanager
#docker rm -fv test.placementexecutive
#docker network rm test.sonata-plugins

#  always abort if an error occurs
set -e
set -x
echo "Running containers"
docker ps -a
echo "test_son-mano-base.sh"
#create test.sonata-plugins network
if ! [[ "$(docker network inspect -f {{.Name}} test.sonata-plugins 2> /dev/null)" == "" ]]
then docker network rm test.sonata-plugins ; fi
docker network create test.sonata-plugins

# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 -p 15672:15672 --name test.broker --net=test.sonata-plugins --network-alias=broker rabbitmq:3-management
# wait a bit for broker startup
while [ true ]
do
	export vhosts=`curl http://localhost:15672/api/vhosts/ -u guest:guest | grep "name"`
    if [ -z $vhosts ]
    then
            echo "broker has not started yet"
    else
            echo "broker has started"
            break
    fi
    sleep 1
done


# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mongo --net=test.sonata-plugins --network-alias=mongo mongo

# wait a bit for db startup
while ! nc -z localhost 27017; do
sleep 1 && echo -n .; # waiting for mongo
done;
sleep 3
# spin up the plugin manager
docker run -d --name test.pluginmanager --net=test.sonata-plugins --network-alias=pluginmanager --restart on-failure \
registry.sonata-nfv.eu:5000/pluginmanager
# wait a bit for manager startup
sleep 10
# spin up the son-mano-base test container and execute its unittests
docker run --name test.sonmanobase --net=test.sonata-plugins --network-alias=sonmanobase \
-v '/var/run/docker.sock:/var/run/docker.sock' \
registry.sonata-nfv.eu:5000/sonmanobase py.test -v

echo "done. #test_son-mano-base"

## setup cleanup mechanism
#trap "set +e; docker rm -fv test.broker; docker rm -fv test.sonmanobase" INT TERM EXIT
#
## ensure cleanup
#set +e
#docker rm -fv test.broker
#docker rm -fv test.mongo
#docker rm -fv test.pluginmanager
#docker rm -fv test.sonmanobase
#
##  always abort if an error occurs
#set -e
#
#echo "test_son-mano-base.sh"
## spin up container with broker (in daemon mode)
#docker run -d -p 5672:5672 --name test.broker rabbitmq:3
## wait a bit for broker startup
#while ! nc -z localhost 5672; do
#sleep 1 && echo -n .; # waiting for rabbitmq
#done;
#sleep 5
## spin up the son-mano-base test container and execute its unittests
#docker run --link test.broker:broker -v '/var/run/docker.sock:/var/run/docker.sock' --name test.sonmanobase registry.sonata-nfv.eu:5000/sonmanobase py.test -v
#
#echo "done."
