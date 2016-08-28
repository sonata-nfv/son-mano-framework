FROM python:3.4-slim
MAINTAINER SONATA


# define plugin name once
ENV PLUGIN_BASE son-mano-specific-manager-registery

# configrurations
ENV mongo_host mongo
ENV mongo_port 27017
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel
ENV DOCKER_HOST unix://var/run/docker.sock


ADD son-mano-base /son-mano-base
ADD son-mano-specific-manager-registry /son-mano-specific-manager-registry
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-specific-manager-registry
RUN pip3 install docker-py
RUN python setup.py develop

CMD ["son_mano_specific_manager_registry"]

