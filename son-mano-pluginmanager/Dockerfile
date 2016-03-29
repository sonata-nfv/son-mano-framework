FROM python:3.4-slim
MAINTAINER SONATA

# configrurations
ENV mongo_host mongo

ADD son-mano-base /son-mano-base
ADD son-mano-pluginmanager /son-mano-pluginmanager
ADD son-mano-pluginmanager/broker.config /etc/son-mano/broker.config
ADD utils/delayedstart.sh /delayedstart.sh


WORKDIR /son-mano-base
RUN python setup.py install

WORKDIR /son-mano-pluginmanager

# we need to reset the __pycache__ for correct test discovery
RUN rm -rf test/__pycache__
RUN python setup.py develop

CMD ["son-mano-pluginmanager"]

