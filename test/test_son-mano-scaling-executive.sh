#!/bin/sh
# limitations under the License.
#
# Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.
#
# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

#
# This script runs the son-mano-scaling-executive plugin related tests.
#
# It starts four Docker containers:
# - RabbitMQ
# - MongoDB
# - son-mano-pluginmanager/Dockerfile
# - plugin/son-mano-service-lifecycle-management/Dockerfile
#
# It triggers the unittest execution in plugin/son-mano-service-lifecycle-management
#

# setup cleanup mechanism
trap "set +e; docker rm -fv test.broker; docker rm -fv test.mongo; docker rm -fv test.pluginmanager; docker rm -fv test.scalingexecutive; " INT TERM EXIT

# ensure cleanup
set +e
docker rm -fv test.broker
docker rm -fv test.mongo
docker rm -fv test.pluginmanager
docker rm -fv test.scalingexecutive

#  always abort if an error occurs
set -e

echo "test_son-mano-scaling-executive.sh"
# spin up container with broker (in daemon mode)
docker run -d -p 5672:5672 --name test.broker rabbitmq:3
# wait a bit for broker startup
while ! nc -z localhost 5672; do
sleep 1 && echo -n .; # waiting for rabbitmq
done;
# spin up container with MongoDB (in daemon mode)
docker run -d -p 27017:27017 --name test.mongo mongo
# wait a bit for db startup
while ! nc -z localhost 27017; do
sleep 1 && echo -n .; # waiting for mongo
done;
sleep 3
# spin up the plugin manager
docker run -d --link test.broker:broker --link test.mongo:mongo --name test.pluginmanager registry.sonata-nfv.eu:5000/pluginmanager
# wait a bit for manager startup
sleep 3
# spin up scaling executive container and run py.test
docker run -it --rm --link test.broker:broker --name test.scalingexecutive registry.sonata-nfv.eu:5000/scalingexecutive py.test -v

echo "done."