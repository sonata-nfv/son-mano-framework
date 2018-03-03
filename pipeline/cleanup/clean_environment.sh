#!/bin/bash

set -e
set -x

echo "Clean dependencies"

#TODO: rename the test ssms and fsms van Hadi

docker rm -fv $(docker ps -a -q -f "name=test.mano.")

docker network rm son-mano-unittests

docker ps -a
docker network ls
