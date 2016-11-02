FROM python:3.4-slim
MAINTAINER SONATA

# configurations
ENV PLUGIN_BASE son-mano-example-placement-ssm
ENV broker_name broker,broker
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel

ADD son-mano-base /son-mano-base
ADD son-mano-specific-manager-registry/ssmplace /ssmplace
ADD utils/delayedstart.sh /delayedstart.sh

WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /ssmplace
RUN python setup.py develop

CMD ["ssmplace"]

