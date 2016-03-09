FROM ubuntu:trusty
MAINTAINER SONATA

# define plugin name once
ENV PLUGIN_BASE son-mano-service-lifecycle-management

# install basic python environment
RUN apt-get update && \
    apt-get install -y python python-dev python-distribute python-pip

# add generic project files
ADD son-mano-base /son-mano-base
ADD utils/delayedstart.sh /delayedstart.sh

# add plugin related files
ADD plugins/${PLUGIN_BASE}/broker.config /etc/son-mano/broker.config
ADD plugins/${PLUGIN_BASE} /plugins/${PLUGIN_BASE}

# install son-mano-base to be able to use the plugin base class etc.
WORKDIR /son-mano-base
RUN python setup.py install

# install actual plugin
WORKDIR /plugins/${PLUGIN_BASE}
RUN python setup.py install

CMD ["${PLUGIN_BASE}"]


