[![Build Status](http://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-mano-framework)](http://jenkins.sonata-nfv.eu/job/son-mano-framework)

# son-mano-framework

SONATA's MANO framework is the core of SONATA's service platform. It consists of a set of loosely coupled components (micro-services) that use a message broker to communicate, thus providing a highly flexible orchestration system. These components are called **MANO plugins** and can easily be replaced to customize the orchestration functionalities of the platform.

The main orchestration functionalities are currently implemented in the [service lifecycle management plugin (SLM)](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-service-lifecycle-management) which receives requests from the [gatekeeper](https://github.com/sonata-nfv/son-gkeeper). The SLM uses the [function lifecycle management plugin (FLM)](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-function-lifecycle-management) to perform the tasks on the level of the vnf and the [specific manager registry (SMR)](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-specificmanager) for customised life cycle events that are embedded in service specific managers (SSMs) and function specific managers (FSMs). These SSMs and FSMs are processes created by the developer of the service which customise life cycle events of the service or vnf they are attached to. The SLM and FLM create and maintain records for the deployed services and vnfs by using [repositories](https://github.com/sonata-nfv/son-catalogue-repos) and the SLM informs the [Monitoring Manager](https://github.com/sonata-nfv/son-monitor) when a new service or vnfs should be monitored. The SLM and the FLM use the [infrastructure adaptor (IA)](https://github.com/sonata-nfv/son-sp-infrabstract) for all instructions and requests related to the VIMs and WIMs.

The MANO framework exposes the following workflows, through the GK, to the user:

* Instantiate a service
* Terminate a running service instance

The MANO framework exposes the following life cycle events to be customised/overwritten by SSMs and FSMs:

* The placement of a service (Placement SSM)
* The configuration of a service (Configure SSM)
* The schedule of a workflow (Task SSM)
* Start, stop, configure and scale events for a single VNF (Start/Stop/Configure/Scale FSM)
* Reaction by the MANO Framework on received Monitoring information (Monitoring SSM)

More details on these processes can be found in the wiki. The overall SONATA service platform architecture is available on the website:

* [SONATA Architecture](http://sonata-nfv.eu/content/architecture)
* [SONATA Architecture Deliverable 2.2](http://sonata-nfv.eu/sites/default/files/sonata/public/content-files/pages/SONATA_D2.2_Architecture_and_Design.pdf)

## Development

SONATA's MANO framework is designed and implemented with micro-services. The following micro-services are currently implemented:

1. [`son-mano-base`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-base): not a standalone service but a collection of base classes that are used by the other MANO plugins, also contains a message abstraction layer that encapsulates the RabbitMQ related communication code;
2. [`son-mano-pluginmanager`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-pluginmanager): every MANO plugin registers to this service, the PM provides a CLI to control and monitor active plugins;
3. [`plugins/son-mano-service-lifecycle-management`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-service-lifecycle-management): main orchestration component, manages the lifecycle of the serivces;
4. [`plugins/son-mano-function-lifecycle-management`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-function-lifecycle-management): manages the lifecycle of the individual vnfs, based on instructions from the SLM;
5. [`plugins/son-mano-placement-executive`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-placement-executive): manages the communication between placement SSMs and the core of the MANO framework;
6. [`son-mano-specificmanager`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-specificmanager): manages the lifecycle of the SSMs and FSMs;
7. [`plugins/son-mano-placement`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-placement):  provides the in-house placement algorithm, if the placement for a service needs to be calculated and there was no Placement SSM provided by the developer, this plugin is used;

Each of these components is entirely implemented in Python.

### Building

Each micro-service of the framework is executed in its own Docker container. So 'building' the framework becomes building all the containers. The build steps for this are described in a `Dockerfile` that is placed in the folder of each micro service. Building the containers goes is done as follows:


1. `docker build -t sonatanfv/pluginmanager -f son-mano-pluginmanager/Dockerfile .`
2. `docker build -t sonatanfv/servicelifecyclemanagement -f plugins/son-mano-service-lifecycle-management/Dockerfile .`
3. `docker build -t sonatanfv/functionlifecyclemanagement -f plugins/son-mano-function-lifecycle-management/Dockerfile .`
4. `docker build -t sonatanfv/specificmanagerregistry -f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .`
5. `docker build -t sonatanfv/placementexecutive -f plugins/son-mano-placement-executive/Dockerfile .`
6. `docker build -t sonatanfv/placementplugin -f plugins/son-mano-placement/Dockerfile .`

### Dependencies

Son-mano-framework expects the following environment:

* Python 3.4
* [Docker](https://www.docker.com) >= 1.10 (Apache 2.0)
* [RabbitMQ](https://www.rabbitmq.com) >= 3.5 (Mozilla Public License)
* [MongoDB](https://www.mongodb.com/community) >= 3.2 (AGPLv3)

Son-mano-framework has the following dependencies:

* [amqpstorm](https://pypi.python.org/pypi/AMQPStorm) >= 1.4 (MIT)
* [argparse](https://pypi.python.org/pypi/argparse) >= 1.4.0 (Python software foundation License)
* [docker-py](https://pypi.python.org/pypi/docker-py) == 1.7.1(Apache 2.0)
* [Flask](https://pypi.python.org/pypi/Flask) >= 0.11 (BSD)
* [flask_restful](https://pypi.python.org/pypi/Flask-RESTful) >= 0.3 (BSD)
* [mongoengine](https://pypi.python.org/pypi/mongoengine) >= 0.10.6 (MIT)
* [pytest-runner](https://pypi.python.org/pypi/pytest-runner) >= 2.8 (MIT)
* [pytest](https://pypi.python.org/pypi/pytest) >= 2.9 (MIT)
* [PyYAML](https://pypi.python.org/pypi/PyYAML) >= 3.11 (MIT)
* [requests](https://pypi.python.org/pypi/requests) >= 2.10 (Apache 2.0)
* [pycrypto](https://pypi.python.org/pypi/pycrypto) >= 2.6.1 (Public Domain)

### Contributing
Contributing to the son-mano-framework is really easy. You must:

1. Fork [this repository](http://github.com/sonata-nfv/son-mano-framework);
2. Work on your proposed changes, preferably through submiting [issues](https://github.com/sonata-nfv/son-mano-framework/issues);
3. Push changes on your fork;
3. Submit a Pull Request;
4. Follow/answer related [issues](https://github.com/sonata-nfv/son-mano-framework/issues) (see Feedback-Chanel, below).

## Installation

If you do not want to execute the components within a Docker container, you can also install them on a normal machine. Each micro-service contains a `setup.py` file so that you can follow the standard Python installation procedure by doing:

```
python setup.py install
```

or 

```
python setup.py develop
```

## Usage

To run all components of the MANO framework you have to start their containers. Additionally, a container that runs RabbitMQ and a container that runs MongoDB has to be started. A docker network is facilitating the connections between the containers.

1. `docker network create sonata`
2. `docker run -d -p 5672:5672 --name broker --net=sonata rabbitmq:3-management`
3. `docker run -d -p 27017:27017 --name mongo --net=sonata mongo`
4. `HOSTIP=<hosting_ip>`
5. `docker run -d --name pluginmanager --net=sonata --network-alias=pluginmanager -p 8001:8001 -e mongo_host=$HOSTIP -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/pluginmanager`
6. `docker run -d --name servicelifecyclemanagement --net=sonata --network-alias=servicelifecyclemanagement -e url_nsr_repository=http://$HOSTIP:4002/records/nsr/ -e url_vnfr_repository=http://$HOSTIP:4002/records/vnfr/ -e url_monitoring_server=http://$HOSTIP:8000/api/v1/ -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/servicelifecyclemanagement`
7. `docker run -d --name functionlifecyclemanagement --net=sonata --network-alias=functionlifecyclemanagement -e url_vnfr_repository=http://$HOSTIP:4002/records/vnfr/ -e url_monitoring_server=http://$HOSTIP:8000/api/v1/ -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/functionlifecyclemanagement`
8. `docker run -d --name placementplugin --net=sonata --network-alias=placementplugin -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/placementplugin`
9. `docker run -d --name placementexecutive --net=sonata --network-alias=placementexecutive -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/placementexecutive`
10. `docker run -d --name specificmanagerregistry --net=sonata --network-alias=specificmanagerregistry -e network_id=sonata -e broker_host=amqp://guest:guest@broker:5672/%2F -e broker_man_host=http://broker:15672 -e sm_broker_host=amqp://specific-management:sonata@broker:5672 -v '/var/run/docker.sock:/var/run/docker.sock' sonatanfv/specificmanagerregistry`

The parameter `broker_host` provides the url on which the message broker can be found. It is build as `amqp://<username>:<password>@<broker_name>:5672/%2F`. 

With the deployment of the SLM and FLM, it is possible to add some ENV parameters, to indicate the urls where the repositories are located. These parameters are optional, and only useful if the MANO framework is used inside the full setup of the SONATA service platform.

Runtime information for these docker containers can be accessed through the standard docker commands:

1. `docker logs <docker_name>`
2. `docker attach <docker_name>`

### Unit tests
#### Container-based unit tests

This is how the Jenkins CI runs the unit tests:

* `./run_tests.sh`

This script builds all required containers, starts them, and executes the unit tests within them.

#### Manual unit tests

Runs unit tests on a local installation.

* NOTICE: The tests need a running RabbitMQ broker to test the messaging subsystem! Without this, tests will fail.
* `cd son-mano-framework`
* `py.test -v son-mano-base/`


## License

Son-mano-framework is published under Apache 2.0 license. Please see the LICENSE file for more details.

## Useful Links

* Paper: [SONATA: Service Programming and Orchestration for Virtualized Software Networks](http://arxiv.org/abs/1605.05850)

---
#### Lead Developers

The following lead developers are responsible for this repository and have admin rights. They can, for example, merge pull requests.

* Thomas Soenen (https://github.com/tsoenen)
* Hadi Razzaghi Kouchaksaraei (https://github.com/hadik3r)
* Manuel Peuster (https://github.com/mpeuster)
* Felipe Vicens (https://github.com/felipevicens)
* Adrian Rosello (https://github.com/adrian-rosello)
* Sharon Mendel-Brin (https://github.com/mendel) 

#### Feedback-Chanel

* You may use the mailing list [sonata-dev@lists.atosresearch.eu](mailto:sonata-dev@lists.atosresearch.eu)
* [GitHub issues](https://github.com/sonata-nfv/son-mano-framework/issues)
