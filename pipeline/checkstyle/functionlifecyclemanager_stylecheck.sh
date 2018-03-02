#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/app/reports/"  registry.sonata-nfv.eu:5000/functionlifecyclemanagement pycodestyle /plugins > reports/checkstyle-functionlifecyclemanager.txt