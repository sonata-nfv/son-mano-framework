FROM ubuntu:trusty
MAINTAINER Manuel Peuster <manuel.peuster@upb.de>


RUN apt-get update && \
    apt-get install -y python python-dev python-distribute python-pip

ADD son-mano-base /son-mano-base
ADD son-mano-base/broker.config /etc/son-mano/broker.config
ADD delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
# we need to reset the __pycache__ for correct test discovery
RUN rm -rf test/__pycache__
# we need to install in develop mode in order to use py.test
RUN python setup.py develop
# run all discovered unittests
CMD ["py.test",  "-v"]


