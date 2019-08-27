#!/bin/bash

set -e
set -x

docker pull tsoenen/sonmano-slm
docker pull tsoenen/sonmano-flm
docker pull tsoenen/sonmano-plm
docker pull tsoenen/sonmano-smr
docker pull tsoenen/sonmano-emuwrapper
docker pull mpeuster/vim-emu
docker pull mongo
docker pull rabbitmq:3.6.15-management
docker pull sonatanfv/tng-rep:dev
docker pull sonatanfv/tng-cat:dev
