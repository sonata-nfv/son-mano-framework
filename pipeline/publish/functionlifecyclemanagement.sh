#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/functionlifecyclemanagement:latest registry.sonata-nfv.eu:5000/functionlifecyclemanagement":$TAG"

docker push registry.sonata-nfv.eu:5000/functionlifecyclemanagement":$TAG"
