#!/bin/bash

set -e
set -x

echo "Run Plugin Manager, to be used by next unittests"

# execute the container
docker run -d --name test.mano.pluginmanager --net=son-mano-unittests \
--network-alias=pluginmanager --name test.mano.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager

while [ true ];
do
	docker logs --tail 1 test.mano.pluginmanager 2> filename || true
    if  tail filename| grep "INFO:son-mano-base:plugin:Plugin running..." ;
    then
            echo "Plugin Manager is up"
            break
    else
            echo "Plugin Manager not yet up"
            sleep 1

    fi
done

rm filename
