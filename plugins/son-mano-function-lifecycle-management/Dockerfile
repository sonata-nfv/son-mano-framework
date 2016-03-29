FROM python:3.4-slim
MAINTAINER SONATA

# define plugin name once
ENV PLUGIN_BASE son-mano-function-lifecycle-management
# Configuration
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel

# add generic project files
ADD son-mano-base /son-mano-base
ADD utils/delayedstart.sh /delayedstart.sh

# add plugin related files
ADD plugins/${PLUGIN_BASE} /plugins/${PLUGIN_BASE}

# install son-mano-base to be able to use the plugin base class etc.
WORKDIR /son-mano-base
RUN python setup.py install

# install actual plugin
WORKDIR /plugins/${PLUGIN_BASE}
RUN python setup.py install

CMD ["son-mano-function-lifecycle-management"]


