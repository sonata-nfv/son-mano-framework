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
This is SONATA's service lifecycle management plugin
"""

import os

# List of topics that are used by the SLM for its rabbitMQ communication

# With gatekeeper
GK_CREATE = "service.instances.create"
GK_PAUSE = "service.instance.pause"
GK_RESUME = "service.instance.restart"
GK_KILL = "service.instance.terminate"
GK_UPDATE = "service.instances.update"

# With other SLM
MANO_STATE = "mano.share.state"
MANO_CREATE = "mano.instances.create"
MANO_PAUSE = "mano.instance.pause"
MANO_RESUME = "mano.instance.restart"
MANO_KILL = "mano.instance.terminate"
MANO_UPDATE = "mano.instances.update"
MANO_DEPLOY = "mano.function.deploy"

# With gatekeeper or other SLM
WC_CREATE = "*.instances.create"
WC_PAUSE = "*.instance.pause"
WC_RESUME = "*.instance.restart"
WC_KILL = "*.instance.terminate"
WC_UPDATE = "*.instances.update"

# With infrastructure adaptor
IA_DEPLOY = 'infrastructure.function.deploy'
IA_TOPO = 'infrastructure.management.compute.list'
IA_PREPARE = 'infrastructure.service.prepare'
IA_CHAIN = 'infrastructure.service.chain'
IA_CONF_WAN = 'infrastructure.wan.configure'
IA_DECONF_WAN = 'infrastructure.wan.deconfigure'

# With specific manager registry
SRM_ONBOARD = 'specific.manager.registry.ssm.on-board'
SRM_INSTANT = 'specific.manager.registry.ssm.instantiate'
SRM_UPDATE = 'specific.manager.registry.ssm.update'

# With Repositories
# TODO: Secure this get against failure
NSR_REPOSITORY_URL = os.environ.get("url_nsr_repository")
if NSR_REPOSITORY_URL is None:
	NSR_REPOSITORY_URL = "http://api.int.sonata-nfv.eu:4002/records/nsr/"

VNFR_REPOSITORY_URL = os.environ.get("url_vnfr_repository")
if VNFR_REPOSITORY_URL is None:
	VNFR_REPOSITORY_URL = "http://api.int.sonata-nfv.eu:4002/records/vnfr/"

# With Monitoring Manager
# TODO: Secure this get against failure
MONITORING_REPOSITORY_URL = os.environ.get("url_monitoring_server")

# With plugin mananger
PL_STATUS = "platform.management.plugin.status"
