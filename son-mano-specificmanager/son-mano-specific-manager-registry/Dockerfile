# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
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
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

FROM python:3.4-slim
MAINTAINER SONATA

# configrurations

# the id of docker network
ENV network_id sonata

# broker main vhost; used for communication among MANO plugins
ENV broker_host amqp://guest:guest@son-broker:5672/%2F

# broker management host; used for creating vhost, user, and setting permissions
ENV broker_man_host http://son-broker:15672

# specific management vhost; used for communcation between SSMs/FSMs and MANO plugins(SMR,SLM,FLM,Executives)
ENV sm_broker_host amqp://specific-management:sonata@son-broker:5672

#broker exchange name
ENV broker_exchange son-kernel

#docker host
ENV DOCKER_HOST unix://var/run/docker.sock


#ENV network_name broker,broker

RUN apt-get update && apt-get install -y glpk-utils && apt-get install -y python3-pip
RUN apt-get install -y git
RUN pip install git+git://github.com/eandersson/amqpstorm.git@feature/reuse_channels

ADD son-mano-base /son-mano-base
ADD son-mano-specificmanager/son-mano-specific-manager-registry /son-mano-specific-manager-registry
#ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-specific-manager-registry
RUN python setup.py develop

CMD ["son-mano-specific-manager-registry"]

