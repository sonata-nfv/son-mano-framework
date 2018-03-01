#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/specificmanagerregistry -f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .
