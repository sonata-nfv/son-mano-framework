[![Build Status](http://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-mano-framework)](http://jenkins.sonata-nfv.eu/job/son-mano-framework)

# son-mano-framework

SONATA's MANO framework is the core of SONATA's service platform and builds a flexible orchestration system. It consists of a set of loosely coupled components (micro services) that use a message broker to communicate. These components are called MANO plugins and can easily be replaced to customize the orchestration functionalities of the platform.

The main orchestration functionalities are currently implemented in the [service lifecycle management plugin (SLM)](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-service-lifecycle-management) which receives instantiation requests from the [gatekeeper](https://github.com/sonata-nfv/son-gkeeper) and instructs the [infrastructure adapter](https://github.com/sonata-nfv/son-sp-infrabstract) to deploy a service. The SLM is also responsible to create the service and function records in the [repositories](https://github.com/sonata-nfv/son-catalogue-repos) once a service is instantiated and to inform the [Monitoring Manager](https://github.com/sonata-nfv/son-monitor) which metrics to monitor and on which triggers to send an alarm.

More details about the service platform's architecture are available on SONATA's website:

* [SONATA Architecture](http://sonata-nfv.eu/content/architecture)
* [SONATA Architecture Deliverable 2.2](http://sonata-nfv.eu/sites/default/files/sonata/public/content-files/pages/SONATA_D2.2_Architecture_and_Design.pdf)

## Development

SONATA's MANO framework is organized as micro services. The following micro services are currently implemented:

1. [`son-mano-base`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-base): not a standalone service but a collection of base classes that are used by the other MANO plugins, also contains a message abstraction layer that encapsulates the RabbitMQ related communication code
2. [`son-mano-pluginmanager`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-pluginmanager): every MANO plugin registers to this service, the PM provides a CLI to control and monitor active plugins
3. [`plugins/son-mano-service-lifecycle-management`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-service-lifecycle-management): main orchestration component, gets service and function descriptors, instructs the infrastructure adapter to start service components in the infrastructure, stores records on services and functions once instantiated, informs Monitoring Manager
4. [`plugins/son-mano-test-plugin`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-test-plugin): the most simple implementation of a MANO plugin, used for integration tests and as an example for plugin developers
5. [`plugins/son-mano-placement-executive`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-placement-executive): The plugin that manages the communication between placement SSMs and the core of the MANO framework
6. [`plugins/son-mano-scaling-executive`](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-placement-executive): The plugin that manages the communication between scaling SSMs/FSMs and the core of the MANO framework
7. [`son-mano-specificmanager`](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-specificmanager): The plugin that manages the lifecycle of the SSMs and FSMs.

Each of these components is entirely implemented in Python.

### Building

Each micro service of the framework is executed in its own Docker container. So 'building' the framework becomes building all the containers. The build steps for this are described in a `Dockerfile` that is placed in the folder of each micro service. Building the containers goes is done as follows:


1. `docker build -t sonatanfv/pluginmanager -f son-mano-pluginmanager/Dockerfile .`
2. `docker build -t sonatanfv/testplugin -f plugins/son-mano-test-plugin/Dockerfile .`
3. `docker build -t sonatanfv/servicelifecyclemanagement -f plugins/son-mano-service-lifecycle-management/Dockerfile .`
4. `docker build -t sonatanfv/specificmanagerregistry -f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .`
5. `docker build -t sonatanfv/placementexecutive -f plugins/son-mano-placement-executive/Dockerfile .`
6. `docker build -t sonatanfv/scalingexecutive -f plugins/son-mano-scaling-executive/Dockerfile .`


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

### Contributing
Contributing to the son-mano-framework is really easy. You must:

1. Fork [this repository](http://github.com/sonata-nfv/son-mano-framework);
2. Work on your proposed changes, preferably through submiting [issues](https://github.com/sonata-nfv/son-mano-framework/issues);
3. Push changes on your fork;
3. Submit a Pull Request;
4. Follow/answer related [issues](https://github.com/sonata-nfv/son-mano-framework/issues) (see Feedback-Chanel, below).

## Installation

If you do not want to execute the components within a Docker container, you can also install them on a normal machine. Each micro service contains a `setup.py` file so that you can follow the standard Python installation procedure by doing:

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
2. `docker run -d -p 5672:5672 --name broker --net=sonata rabbitmq:3`
3. `docker run -d -p 27017:27017 --name mongo --net=sonata mongo`
4. `docker run -d --name pm --net=sonata -p 8001:8001 -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/pluginmanager`
5. `docker run -d --name slm --net=sonata -e url_nsr_repository=http://localhost:4002/records/nsr/ -e url_vnfr_repository=http://localhost:4002/records/vnfr/ -e url_monitoring_server=http://localhost:8000/api/v1/ -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/servicelifecyclemanagement`
6. `docker run -d --name smr --net=sonata -e broker_name=broker,broker -e broker_host=amqp://guest:guest@broker:5672/%2F -v '/var/run/docker.sock:/var/run/docker.sock' sonatanfv/specificmanagerregistry`
7. `docker run -d --name placeexec --net=sonata -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/placementexecutive`
8. `docker run -d --name scaleexec --net=sonata -e broker_host=amqp://guest:guest@broker:5672/%2F sonatanfv/scalingexecutive`

The parameter `broker_host` provides the url on which the message broker can be found. It is build as `amqp://<username>:<password>@<broker_name>:5672/%2F`. 

With the deployment of the SLM, it is possible to add some parameters to the command, to indicate the urls where the SLM can locate the VNFR, NSR and MONITORING repositories. These parameters are optional, and only useful if the MANO framework is used inside the full setup of the SONATA service platform.

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

* Sharon Mendel-Brin (https://github.com/mendel) 
* Manuel Peuster (https://github.com/mpeuster)
* Felipe Vicens (https://github.com/felipevicens)
* Thomas Soenen (https://github.com/tsoenen)
* Adrian Rosello (https://github.com/adrian-rosello)
* Hadi Razzaghi Kouchaksaraei (https://github.com/hadik3r)

#### Feedback-Chanel

* You may use the mailing list [sonata-dev@lists.atosresearch.eu](mailto:sonata-dev@lists.atosresearch.eu)
* [GitHub issues](https://github.com/sonata-nfv/son-mano-framework/issues)
