#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/sonmanobase -f son-mano-base/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/pluginmanager -f son-mano-pluginmanager/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/servicelifecyclemanagement -f plugins/son-mano-service-lifecycle-management/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/functionlifecyclemanagement -f plugins/son-mano-function-lifecycle-management/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/placementplugin --file plugins/son-mano-placement/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/placementexecutive -f plugins/son-mano-placement-executive/Dockerfile .
docker build -t registry.sonata-nfv.eu:5000/specificmanagerregistry -f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .
