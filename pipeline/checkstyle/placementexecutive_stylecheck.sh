#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement-executive/reports/"  registry.sonata-nfv.eu:5000/placementexecutive sh -c "pycodestyle /plugins > reports/checkstyle-placementexecutive.txt"