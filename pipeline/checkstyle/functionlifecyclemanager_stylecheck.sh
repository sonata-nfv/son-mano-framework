#!/bin/bash

docker run --rm=true -i -v "$(pwd)/reports:/plugins/son-mano-function-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/functionlifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-functionlifecyclemanager.txt"