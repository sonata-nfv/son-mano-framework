#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/placementexecutive:latest registry.sonata-nfv.eu:5000/placementexecutive":$TAG"

docker push registry.sonata-nfv.eu:5000/placementexecutive":$TAG"