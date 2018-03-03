#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement/reports/"  registry.sonata-nfv.eu:5000/placementplugin sh -c "pycodestyle /plugins > reports/checkstyle-placementplugin.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-pluginmanager/reports/"  registry.sonata-nfv.eu:5000/pluginmanager sh -c "pycodestyle /son-mano-pluginmanager > reports/checkstyle-pluginmanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-specific-manager-registry/reports/"  registry.sonata-nfv.eu:5000/specificmanagerregistry sh -c "pycodestyle /son-mano-specific-manager-registry > reports/checkstyle-specificmanagerregistry.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-base/reports/"  registry.sonata-nfv.eu:5000/sonmanobase sh -c "pycodestyle /son-mano-base > reports/checkstyle-sonmanobase.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-service-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/servicelifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-servicelifecyclemanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-function-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/functionlifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-functionlifecyclemanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement-executive/reports/"  registry.sonata-nfv.eu:5000/placementexecutive sh -c "pycodestyle /plugins > reports/checkstyle-placementexecutive.txt"