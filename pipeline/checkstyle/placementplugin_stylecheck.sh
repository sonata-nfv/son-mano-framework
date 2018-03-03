#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement/reports/"  registry.sonata-nfv.eu:5000/placementplugin sh -c "pycodestyle /plugins > reports/checkstyle-placementplugin.txt"