#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/placementexecutive -f plugins/son-mano-placement-executive/Dockerfile .
