#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/app/reports/"  registry.sonata-nfv.eu:5000/servicelifecyclemanagement pycodestyle /plugins > reports/checkstyle-servicelifecyclemanager.txt