#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/placementplugin -f plugins/son-mano-placement/Dockerfile .
