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

#
# Configurations
#
# The topic to which service instantiation requests
# of the GK are published
GK_CREATE = "service.instances.create"
VNF_CREATE = "function.instances.create"

GK_INSTANCE_UPDATE = 'service.instances.update'

# The topic to which service instance deploy replies
# of the Infrastructure Adaptor are published
INFRA_ADAPTOR_INSTANCE_DEPLOY_REPLY_TOPIC = "infrastructure.service.deploy"

# The topic to which available vims are published
INFRA_ADAPTOR_AVAILABLE_VIMS = 'infrastructure.management.compute.list'

# TODO: discuss topic for topology
IA_TOPO = 'infrastructure.management.topology'

# Topics for interaction with the specific manager registry
SRM_ONBOARD = 'specific.manager.registry.ssm.on-board'
SRM_INSTANT = 'specific.manager.registry.ssm.instantiate'
SRM_UPDATE = 'specific.manager.registry.ssm.update'

# The NSR Repository can be accessed through a RESTful
# API. Links are red from ENV variables.
NSR_REPOSITORY_URL = os.environ.get("url_nsr_repository")
VNFR_REPOSITORY_URL = os.environ.get("url_vnfr_repository")

# Monitoring repository, can be accessed throught a RESTful
# API. Link is red from ENV variable.
MONITORING_REPOSITORY_URL = os.environ.get("url_monitoring_server")

# Broadcasts from the Plugin Manager on the status of the plugins
PL_STATUS = "platform.management.plugin.status"
