#!/bin/bash
# this script helps us to delay commands within a docker container in order
# to ensure that other containers (e.g. the broker) have enough time to start
sleep $1
# run command
$2
