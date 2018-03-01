#!/bin/bash
set -e
docker build -t registry.sonata-nfv.eu:5000/sonmanobase -f son-mano-base/Dockerfile .
