FROM python:3.4-slim
MAINTAINER SONATA

# configrurations
ENV mongo_host mongo
ENV mongo_port 27017
ENV broker_host amqp://guest:guest@broker:5672/%2F
ENV broker_exchange son-kernel

ADD son-mano-base /son-mano-base
ADD son-mano-specific-manager-registry/ssm2 /ssm2
ADD son-mano-specific-manager-registry/ssm2/id_rsa /root/.ssh/id_rsa
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install


WORKDIR /ssm2
RUN python setup.py develop
RUN chmod 600 /root/.ssh/id_rsa

CMD ["ssm2"]

