#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/servicelifecyclemanagement:latest registry.sonata-nfv.eu:5000/servicelifecyclemanagement":$TAG"

docker push registry.sonata-nfv.eu:5000/servicelifecyclemanagement":$TAG"
