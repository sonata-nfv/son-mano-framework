FROM python:3.4-slim
MAINTAINER SONATA

# configrurations
ENV mongo_host mongo
ENV mongo_port 27017
ENV network_id sonata-plugins
ENV network_name broker,broker
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_man_host http://broker:15672/
ENV broker_exchange son-kernel
ENV DOCKER_HOST unix://var/run/docker.sock


ADD son-mano-base /son-mano-base
ADD son-mano-specificmanager/son-mano-specific-manager-registry /son-mano-specific-manager-registry
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-specific-manager-registry
RUN python setup.py develop

CMD ["son-mano-specific-manager-registry"]

