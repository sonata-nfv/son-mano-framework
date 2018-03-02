#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/app/reports/"  registry.sonata-nfv.eu:5000/sonmanobase pycodestyle /son-mano-base > reports/checkstyle-sonmanobase.txt