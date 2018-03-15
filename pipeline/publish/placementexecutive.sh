#!/bin/bash
set -e

TAG=$1

if [ "$TAG" == "int" ]; then
	docker tag registry.sonata-nfv.eu:5000/placementexecutive:latest registry.sonata-nfv.eu:5000/placementexecutive:int
fi
docker push registry.sonata-nfv.eu:5000/placementexecutive":$TAG"