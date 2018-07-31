#!/bin/bash
set -e

TAG=$1

docker tag registry.sonata-nfv.eu:5000/sonmanobase:latest registry.sonata-nfv.eu:5000/sonmanobase":$TAG"

docker push registry.sonata-nfv.eu:5000/sonmanobase":$TAG"
