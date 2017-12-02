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


trap "set +e;
# Show containers logs
docker logs test.broker
docker logs test.mongo
docker logs test.pluginmanager
docker logs test.smr
#Remove containers
docker rm -fv test.broker;
docker rm -fv test.mongo;
docker rm -fv test.pluginmanager;
docker rm -fv test.smr" INT TERM EXIT
#docker network rm test.sonata-plugins" INT TERM EXIT

# ensure cleanup
set +e
if ! [[ "$(docker inspect -f {{.State.Running}} test.broker 2> /dev/null)" == "" ]]; then docker rm -fv test.broker ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.mongo 2> /dev/null)" == "" ]]; then docker rm -fv test.mongo ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.pluginmanager 2> /dev/null)" == "" ]]; then docker rm -fv test.pluginmanager ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} test.smr 2> /dev/null)" == "" ]]; then docker rm -fv test.smr ; fi
# ensure f/ssms cleanup
if ! [[ "$(docker inspect -f {{.State.Running}} ssmexample 2> /dev/null)" == "" ]]; then docker rm -fv ssmexample ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonfsmservice1firewallconfiguration1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 2> /dev/null)" == "" ]]; then docker rm -fv sonfsmservice1firewallconfiguration1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonfsmservice1function1dumb1c32b731f-7eea-4afd-9c60-0b0d0ea37eed 2> /dev/null)" == "" ]]; then docker rm -fv sonfsmservice1function1dumb1c32b731f-7eea-4afd-9c60-0b0d0ea37eed ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonfsmservice1function1monitoring1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 2> /dev/null)" == "" ]]; then docker rm -fv sonfsmservice1function1monitoring1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonfsmservice1function1updateddumb1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 2> /dev/null)" == "" ]]; then docker rm -fv sonfsmservice1function1updateddumb1754fe4fe-96c9-484d-9683-1a1e8b9a31a3 ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonssmservice1dumb1937213ae-890b-413c-a11e-45c62c4eee3f 2> /dev/null)" == "" ]]; then docker rm -fv sonssmservice1dumb1937213ae-890b-413c-a11e-45c62c4eee3f ; fi
if ! [[ "$(docker inspect -f {{.State.Running}} sonssmservice1placement1937213ae-890b-413c-a11e-45c62c4eee3f 2> /dev/null)" == "" ]]; then docker rm -fv sonssmservice1placement1937213ae-890b-413c-a11e-45c62c4eee3f ; fi

#docker rm -fv test.broker
#docker rm -fv test.mongo
#docker rm -fv test.pluginmanager
#docker rm -fv test.smr
# ensure f/ssms cleanup
#set +e
#docker rm -fv ssmexample
#docker rm -fv sonfsmservice1firewallconfiguration1
#docker rm -fv sonfsmservice1function1dumb1
#docker rm -fv sonfsmservice1function1monitoring1
#docker rm -fv sonfsmservice1function1updateddumb1
#docker rm -fv sonssmservice1dumb1
#docker rm -fv sonssmservice1placement1
#docker rm -fv sonssmservice1dumb1

#  always abort if an error occurs
set -e
set -x
echo "Running containers"
docker ps -a
echo "test_plugin-son-mano-smr.sh"
#create sonata-plugins network
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

# spin up smr container and run py.test
docker run --name test.smr --net=test.sonata-plugins --network-alias==specificmanagerregistry \
-v '/var/run/docker.sock:/var/run/docker.sock' \
-e network_id=test.sonata-plugins  -e broker_man_host=http://broker:15672 \
-e broker_host=amqp://guest:guest@broker:5672/%2F \
-e sm_broker_host=amqp://specific-management:sonata@broker:5672 \
registry.sonata-nfv.eu:5000/specificmanagerregistry py.test -v

echo "done. #test_plugin-son-mano-smr"
