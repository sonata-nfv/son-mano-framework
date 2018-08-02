# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.

# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

#!/bin/bash

set -e
set -x

echo "Clean up leftovers from SONATA jobs"

docker rm -fv $(docker ps -a -f "network=test.sonata-plugins") || true

echo "Create docker network MANO unittests"

# spin up a docker network
docker network create son-mano-unittests

echo "Run a rabbitmq broker container"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 -p 15672:15672 --name test.mano.broker --net=son-mano-unittests --network-alias=broker rabbitmq:3-management

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

echo "Run a Mongo DB container"
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mano.mongo --net=son-mano-unittests --network-alias=mongo  mongo
# wait a bit for db startup
while ! nc -z localhost 27017; do
sleep 1 && echo -n .; # waiting for mongo
done;

echo "Dependencies setup completed"
