#!/bin/bash
set -e
docker push registry.sonata-nfv.eu:5000/sonmanobase
docker push registry.sonata-nfv.eu:5000/pluginmanager
docker push registry.sonata-nfv.eu:5000/servicelifecyclemanagement
docker push registry.sonata-nfv.eu:5000/functionlifecyclemanagement
docker push registry.sonata-nfv.eu:5000/placementplugin
docker push registry.sonata-nfv.eu:5000/placementexecutive
docker push registry.sonata-nfv.eu:5000/specificmanagerregistry