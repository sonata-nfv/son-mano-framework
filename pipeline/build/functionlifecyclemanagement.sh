#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/functionlifecyclemanagement -f plugins/son-mano-function-lifecycle-management/Dockerfile .
