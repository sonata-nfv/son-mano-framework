FROM python:3.4-slim
MAINTAINER SONATA

# Configuration
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel

ADD son-mano-base /son-mano-base
ADD utils/delayedstart.sh /delayedstart.sh
ADD test/misc /son-mano-base/test/misc


WORKDIR /son-mano-base

# we need to install in develop mode in order to use py.test
RUN python setup.py develop
# run all discovered unittests
CMD ["py.test",  "-v"]


