FROM ubuntu:trusty
MAINTAINER Manuel Peuster <manuel.peuster@upb.de>


RUN apt-get update && \
    apt-get install -y python python-dev python-distribute python-pip nmap

ADD son-mano-base /son-mano-base
ADD son-mano-pluginmanager /son-mano-pluginmanager
ADD son-mano-pluginmanager/broker.config /etc/son-mano/broker.config
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-pluginmanager
RUN python setup.py install

CMD ["son-mano-pluginmanager"]

