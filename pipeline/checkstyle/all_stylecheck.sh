# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Neither the name of the SONATA-NFV, 5GTANGO
# nor the names of its contributors may be used to endorse or promote
# products derived from this software without specific prior written
# permission.

# This work has been performed in the framework of the SONATA project,
# funded by the European Commission under Grant number 671517 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the SONATA
# partner consortium (www.sonata-nfv.eu).

# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).

#!/bin/bash

docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement/reports/"  registry.sonata-nfv.eu:5000/placementplugin sh -c "pycodestyle /plugins > reports/checkstyle-placementplugin.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-pluginmanager/reports/"  registry.sonata-nfv.eu:5000/pluginmanager sh -c "pycodestyle /son-mano-pluginmanager > reports/checkstyle-pluginmanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-specific-manager-registry/reports/"  registry.sonata-nfv.eu:5000/specificmanagerregistry sh -c "pycodestyle /son-mano-specific-manager-registry > reports/checkstyle-specificmanagerregistry.txt"
docker run -i --rm=true -v "$(pwd)/reports:/son-mano-base/reports/"  registry.sonata-nfv.eu:5000/sonmanobase sh -c "pycodestyle /son-mano-base > reports/checkstyle-sonmanobase.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-service-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/servicelifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-servicelifecyclemanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-function-lifecycle-management/reports/"  registry.sonata-nfv.eu:5000/functionlifecyclemanagement sh -c "pycodestyle /plugins > reports/checkstyle-functionlifecyclemanager.txt"
docker run -i --rm=true -v "$(pwd)/reports:/plugins/son-mano-placement-executive/reports/"  registry.sonata-nfv.eu:5000/placementexecutive sh -c "pycodestyle /plugins > reports/checkstyle-placementexecutive.txt"