#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/placementplugin:latest registry.sonata-nfv.eu:5000/placementplugin":$TAG"

docker push registry.sonata-nfv.eu:5000/placementplugin":$TAG"
