FROM ubuntu:trusty
MAINTAINER Manuel Peuster <manuel.peuster@upb.de>


RUN apt-get update && \
    apt-get install -y python python-dev python-distribute python-pip

ADD son-mano-base /son-mano-base
ADD son-mano-base/broker.config /etc/son-mano/broker.config
ADD delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

CMD ["nosetests",  "-s", "-v"]


