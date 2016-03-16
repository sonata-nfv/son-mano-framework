FROM python:3.4-slim
MAINTAINER SONATA

# define plugin name once
ENV PLUGIN_BASE son-mano-service-lifecycle-management

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
RUN python setup.py develop

# we need to reset the __pycache__ for correct test discovery
RUN rm -rf /plugins/${PLUGIN_BASE}test/__pycache__

CMD ["son-mano-service-lifecycle-management"]


