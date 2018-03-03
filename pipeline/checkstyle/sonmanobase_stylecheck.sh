#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/son-mano-base/reports/"  registry.sonata-nfv.eu:5000/sonmanobase sh -c "pycodestyle /son-mano-base > reports/checkstyle-sonmanobase.txt"