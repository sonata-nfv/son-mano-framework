#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/son-mano-pluginmanager/reports/"  registry.sonata-nfv.eu:5000/pluginmanager sh -c "pycodestyle /son-mano-pluginmanager > reports/checkstyle-pluginmanager.txt"