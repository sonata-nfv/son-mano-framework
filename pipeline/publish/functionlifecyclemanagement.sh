#!/bin/bash
set -e

TAG=$1

if [ "$TAG" == "int" ]; then
	echo "Retagging"
	docker tag registry.sonata-nfv.eu:5000/functionlifecyclemanagement:latest registry.sonata-nfv.eu:5000/functionlifecyclemanagement:int
fi

docker push registry.sonata-nfv.eu:5000/functionlifecyclemanagement":$TAG"
