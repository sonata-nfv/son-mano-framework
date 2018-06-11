#!/bin/bash
set -e
docker tag registry.sonata-nfv.eu:5000/functionlifecyclemanagement:latest registry.sonata-nfv.eu:5000/functionlifecyclemanagement:int
docker tag registry.sonata-nfv.eu:5000/placementexecutive:latest registry.sonata-nfv.eu:5000/placementexecutive:int
docker tag registry.sonata-nfv.eu:5000/placementplugin:latest registry.sonata-nfv.eu:5000/placementplugin:int
docker tag registry.sonata-nfv.eu:5000/pluginmanager:latest registry.sonata-nfv.eu:5000/pluginmanager:int
docker tag registry.sonata-nfv.eu:5000/servicelifecyclemanagement:latest registry.sonata-nfv.eu:5000/servicelifecyclemanagement:int
docker tag registry.sonata-nfv.eu:5000/sonmanobase:latest registry.sonata-nfv.eu:5000/sonmanobase:int
docker tag registry.sonata-nfv.eu:5000/specificmanagerregistry:latest registry.sonata-nfv.eu:5000/specificmanagerregistry:int
