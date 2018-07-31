#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/pluginmanager:latest registry.sonata-nfv.eu:5000/pluginmanager":$TAG"

docker push registry.sonata-nfv.eu:5000/pluginmanager":$TAG"
