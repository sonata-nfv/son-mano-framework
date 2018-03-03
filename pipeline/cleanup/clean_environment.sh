#!/bin/bash

set -e
set -x

echo "Clean dependencies"

docker ps -a

docker rm -fv $(docker ps -a -q -f "network=son-mano-unittests") || true

docker network rm son-mano-unittests || true

docker ps -a
docker network ls
