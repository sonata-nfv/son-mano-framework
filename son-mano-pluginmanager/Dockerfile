FROM python:3.4-slim
MAINTAINER SONATA

ADD son-mano-base /son-mano-base
ADD son-mano-pluginmanager /son-mano-pluginmanager
ADD son-mano-pluginmanager/broker.config /etc/son-mano/broker.config
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-pluginmanager
RUN python setup.py install

CMD ["son-mano-pluginmanager"]

