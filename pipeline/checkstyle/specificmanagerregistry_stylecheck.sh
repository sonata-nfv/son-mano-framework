#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/app/reports/"  registry.sonata-nfv.eu:5000/specificmanagerregistry pycodestyle /son-mano-specific-manager-registry > reports/checkstyle-specificmanagerregistry.txt