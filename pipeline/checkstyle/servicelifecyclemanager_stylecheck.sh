#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-service-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/servicelifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-servicelifecyclemanager.txt"