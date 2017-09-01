"""
Copyright (c) 2015 SONATA-NFV
ALL RIGHTS RESERVED.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
    http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
Neither the name of the SONATA-NFV [, ANY ADDITIONAL AFFILIATION]
nor the names of its contributors may be used to endorse or promote
products derived from this software without specific prior written
permission.
This work has been performed in the framework of the SONATA project,
funded by the European Commission under Grant number 671517 through
the Horizon 2020 and 5G-PPP programmes. The authors would like to
acknowledge the contributions of their colleagues of the SONATA
partner consortium (www.sonata-nfv.eu).a
"""
"""
This is SONATA's function lifecycle management plugin
"""

import os
from urllib.parse import urlparse

# List of topics that are used by the FLM for its rabbitMQ communication

# With the FLM
VNF_DEPLOY = "mano.function.deploy"
VNF_START = "mano.function.start"
VNF_CONFIG = "mano.function.configure"
VNF_STOP = "mano.function.stop"
VNF_SCALE = "mano.function.scale"
VNF_KILL = "mano.function.terminate"

# With infrastructure adaptor
IA_DEPLOY = 'infrastructure.function.deploy'

# With specific manager registry
SRM_ONBOARD = 'specific.manager.registry.fsm.on-board'
SRM_INSTANT = 'specific.manager.registry.fsm.instantiate'
SRM_UPDATE = 'specific.manager.registry.fsm.update'

# REST APIs
temp = os.environ.get("url_gk_api")
if temp is None:
    temp = "http://son-gtkapi:5000/api/v2/"
p = urlparse(temp)
GK_PORT = p.port
BASE_URL = p.scheme + "://" + p.hostname + ":" + str(GK_PORT)

# REST API with GK
GK_SERVICES_URL = BASE_URL + '/api/v2/services/'
GK_FUNCTIONS_URL = BASE_URL + '/api/v2/functions/'

# With Repositories
temp = os.environ.get("url_vnfr_repository")
if temp is None:
    temp = "http://son-catalogue-repos:4011/records/vnfr/"
c = urlparse(temp)
CAT_PORT = c.port
CAT_BASE_URL = c.scheme + "://" + c.hostname + ":" + str(CAT_PORT)

NSR_REPOSITORY_URL = CAT_BASE_URL + "/records/nsr/"
VNFR_REPOSITORY_URL = CAT_BASE_URL + "/records/vnfr/"

# With Monitoring Manager
# TODO: Secure this get against failure
MONITORING_URL = os.environ.get("url_monitoring_server")
