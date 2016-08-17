FROM python:3.4-slim
MAINTAINER SONATA

# configrurations
ENV mongo_host mongo
ENV mongo_port 27017
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel


ADD son-mano-base /son-mano-base
ADD son-mano-specific-manger-registry/ssm1 /ssm1
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /ssm1
RUN python setup.py develop

CMD ["ssm1"]

