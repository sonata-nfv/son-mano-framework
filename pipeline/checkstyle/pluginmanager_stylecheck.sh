#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/app/reports/"  registry.sonata-nfv.eu:5000/pluginmanager pycodestyle /son-mano-pluginmanager > reports/checkstyle-pluginmanager.txt