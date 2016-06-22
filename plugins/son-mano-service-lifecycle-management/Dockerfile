FROM python:3.4-slim
MAINTAINER SONATA

# define plugin name once
ENV PLUGIN_BASE son-mano-service-lifecycle-management
# Configuration
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel

ENV url_nsr_repository http://api.int.sonata-nfv.eu:4002/records/nsr/
ENV url_vnfr_repository http://api.int.sonata-nfv.eu:4002/records/vnfr/
ENV url_monitoring_server http://sp.int3.sonata-nfv.eu:8000/api/v1/

# add generic project files
ADD son-mano-base /son-mano-base
ADD utils/delayedstart.sh /delayedstart.sh

# add plugin related files
ADD plugins/${PLUGIN_BASE} /plugins/${PLUGIN_BASE}
#Remove this line later, and remove files in directory
#ADD plugins/${PLUGIN_BASE}/son_mano_slm/test_descriptors /test_descriptors

# install son-mano-base to be able to use the plugin base class etc.
WORKDIR /son-mano-base
RUN python setup.py install

# install actual plugin
WORKDIR /plugins/${PLUGIN_BASE}
RUN python setup.py develop


CMD ["son-mano-service-lifecycle-management"]


