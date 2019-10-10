# Copyright (c) 2015 SONATA-NFV, 2017 5GTANGO
# ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Neither the name of the SONATA-NFV, 5GTANGO
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
# This work has been performed in the framework of the 5GTANGO project,
# funded by the European Commission under Grant number 761493 through
# the Horizon 2020 and 5G-PPP programmes. The authors would like to
# acknowledge the contributions of their colleagues of the 5GTANGO
# partner consortium (www.5gtango.eu).
"""
This is SONATA's service lifecycle management plugin
"""

import os
from urllib.parse import urlparse

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
MANO_REMOVE = "mano.function.remove"
MANO_UPDATE = "mano.instances.update"
MANO_DEPLOY = "mano.function.deploy"
MANO_PLACE = "mano.service.place"
MANO_START = "mano.function.start"
MANO_CONFIG = "mano.function.configure"
MANO_STOP = "mano.function.stop"
MANO_SCALE = "service.instance.scale"
MANO_MIGRATE = "service.instance.migrate"
MANO_RECONFIGURE = "service.instance.reconfigure"
MANO_STATE = "mano.function.state"

# With gatekeeper or other SLM
WC_CREATE = "*.instances.create"
WC_PAUSE = "*.instance.pause"
WC_RESUME = "*.instance.restart"
WC_KILL = "*.instance.terminate"
WC_UPDATE = "*.instances.update"

# With infrastructure adaptor
IA_CREATE_NETWORKS = 'infrastructure.service.network.create'
IA_REMOVE_NETWORKS = 'infrastructure.service.network.delete'
IA_DEPLOY = 'infrastructure.function.deploy'
IA_REMOVE = 'infrastructure.service.remove'
IA_VIM_LIST = 'infrastructure.management.compute.list'
IA_WIM_LIST = 'infrastructure.management.wan.list'
IA_TOPO = 'infrastructure.management.compute.list'
IA_PREPARE = 'infrastructure.service.prepare'
IA_CONF_CHAIN = 'infrastructure.service.chain.configure'
IA_DECONF_CHAIN = 'infrastructure.service.chain.deconfigure'
IA_CONF_WAN = 'infrastructure.service.wan.configure'
IA_DECONF_WAN = 'infrastructure.service.wan.deconfigure'

# With specific manager registry
SRM_ONBOARD = 'specific.manager.registry.ssm.on-board'
SRM_INSTANT = 'specific.manager.registry.ssm.instantiate'
SRM_UPDATE = 'specific.manager.registry.ssm.update'
SSM_TERM = 'specific.manager.registry.ssm.terminate'
FSM_TERM = 'specific.manager.registry.fsm.terminate'

OPERATOR_POLICY = 'policy.operator'

# With Executive
EXEC_PLACE = 'placement.executive.request'

# With plugin mananger
PL_STATUS = "platform.management.plugin.status"

# With monitoring
MON_RECEIVE = "son.monitoring"
FROM_MON_SSM = "monitor.ssm."

# Catalogue urls
cat_path = os.environ.get("cat_path").strip("/")
nsd_ext = os.environ.get("nsd_collection").strip("/")
vnfd_ext = os.environ.get("vnfd_collection").strip("/")

nsd_path = cat_path + '/' + nsd_ext
vnfd_path = cat_path + '/' + vnfd_ext

# Repository urls
repo_path = os.environ.get("repo_path").strip("/")
nsr_ext = os.environ.get("nsr_collection").strip("/")
vnfr_ext = os.environ.get("vnfr_collection").strip("/")

nsr_path = repo_path + '/' + nsr_ext
vnfr_path = repo_path + '/' + vnfr_ext

# Monitoring urls
if os.environ.get("monitoring_path"):
	monitoring_path = os.environ.get("monitoring_path").strip("/")
else:
	monitoring_path = None

# Logger
json_logger = False
if os.environ.get("json_logger"):
	json_logger = True
