#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/specificmanagerregistry:latest registry.sonata-nfv.eu:5000/specificmanagerregistry":$TAG"

docker push registry.sonata-nfv.eu:5000/specificmanagerregistry":$TAG"
