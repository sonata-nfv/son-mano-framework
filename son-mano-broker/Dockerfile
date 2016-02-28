FROM ubuntu:trusty
MAINTAINER Manuel Peuster <manuel.peuster@upb.de>

# Install RabbitMQ
RUN apt-get update && \
    apt-get install -y wget && \
    wget https://www.rabbitmq.com/rabbitmq-signing-key-public.asc && \
    apt-key add rabbitmq-signing-key-public.asc && \
    echo "deb http://www.rabbitmq.com/debian/ testing main" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y rabbitmq-server && \
    rm -rf /var/lib/apt/lists/* && \
    rabbitmq-plugins enable rabbitmq_management

COPY son-mano-broker/rabbitmq.config /etc/rabbitmq/rabbitmq.config

CMD ["rabbitmq-server"]

EXPOSE 5672 15672