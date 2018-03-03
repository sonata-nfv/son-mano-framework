#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/son-mano-specific-manager-registry/reports/"  registry.sonata-nfv.eu:5000/specificmanagerregistry sh -c "pycodestyle /son-mano-specific-manager-registry > reports/checkstyle-specificmanagerregistry.txt"