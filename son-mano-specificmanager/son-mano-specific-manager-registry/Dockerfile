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



ADD son-mano-base /son-mano-base
ADD son-mano-specificmanager/son-mano-specific-manager-registry /son-mano-specific-manager-registry
#ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-specific-manager-registry
RUN python setup.py develop

CMD ["son-mano-specific-manager-registry"]

