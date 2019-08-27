[![Build Status](https://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-mano-framework-pipeline/master)](https://jenkins.sonata-nfv.eu/job/son-mano-framework-pipeline/job/master/)
[![Join the chat at https://gitter.im/sonata-nfv/5gtango-sp](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/sonata-nfv/5gtango-sp)
 
 <p align="center"><img src="https://github.com/sonata-nfv/tng-api-gtw/wiki/images/sonata-5gtango-logo-500px.png" /></p>

The MANO Framework is at the core of [**SONATA's (powered by 5GTANGO)**](https://5gtango.eu/) service platform. It manages and orchestrates the available compute and networking resources to satisfy the requests it receives. As of now, the supported requests are (API description can be found in the [wiki]())

* instantiate a service,
* scale out/in a service instance,
* migrate (part of) a service instance,
* and terminate a service instance.

It is possible for network service and VNF developers to customise the workflows associated to the supported requests. Through a mechanism of specific managers, the behaviour of the MANO Framework can be altered on a per service/vnf basis. More information on this can be found in the [wiki](https://github.com/sonata-nfv/son-mano-framework/wiki/Service-and-Function-Specific-Managers).

The MANO Framework functionaity is build from a set of loosely coupled components (micro-services) which use a message broker to communicate. The main orchestration functionalities are currently implemented in the [service lifecycle management plugin (SLM)](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-service-lifecycle-management). The SLM uses the [function lifecycle management plugin (FLM)](https://github.com/sonata-nfv/son-mano-framework/tree/master/plugins/son-mano-function-lifecycle-management) to perform orchestration tasks on the level of the VNF and the [specific manager registry (SMR)](https://github.com/sonata-nfv/son-mano-framework/tree/master/son-mano-specificmanager) for customised events that are embedded in service specific managers (SSMs) and function specific managers (FSMs). The [Placement Plugin](https://github.com/sonata-nfv/son-mano-framework/wiki/Placement-Plugin) performs all calculations related to optimising the resources usage.

Some useful links:

* [Communications Magazine paper on specific managers](https://ieeexplore.ieee.org/abstract/document/8713806)
* [5GTANGO Service Platform Deliverable 5.1](https://5gtango.eu/project-outcomes/deliverables/43-d5-1-service-platform-operational-first-prototype.html)
* [SONATA Architecture Deliverable 2.3](https://5gtango.eu/project-outcomes/deliverables/61-d2-3-updated-requirements,-architecture-design-and-v-v-elements)

# Development

Each MANO Framework component is written in Python, and can be packaged as a Docker container. To build the respective Docker containers, use

```bash
docker build -f plugins/son-mano-service-lifecycle-management/Dockerfile .
docker build -f plugins/son-mano-function-lifecycle-management/Dockerfile .
docker build -f plugins/son-mano-placement/Dockerfile .
docker build -f plugins/son-mano-specific-registry/Dockerfile .
```
or pull them from

```bash
docker pull tsoenen/sonmano-slm
docker pull tsoenen/sonmano-flm
docker pull tsoenen/sonmano-smr
docker pull tsoenen/sonmano-plm
```

# Installation and usage

The MANO Framework was developed in the scope of the **SONATA's (powered by 5GTANGO)** Service Platform. To install the entire platform, follow directions listed in [tng-devops](https://github.com/sonata-nfv/tng-devops).

It is possible to use a standalone version of the MANO Framework, without the other 5GTANGO components. `/install` contains an ansible-playbook that deploys a standalone version of the MANO Framework locally, together with its dependencies:

* A RabbitMQ message broker, used by the MANO components to communicate
* The Catalogue and a Repository, which are used by the MANO Framework to store and fetch descriptors and records
* A Mongo DB, for the Catalogue and Repository to use
* [The Emulator](https://github.com/sonata-nfv/son-emu), which uses local resources to emulate computing and networking resources
* [The Emulator Wrapper](https://github.com/sonata-nfv/tng-sp-ia-emu), to attach the emulator to the MANO Framework

To deploy the standalone MANO Framework, run

```bash
git clone https://github.com/sonata-nfv/son-mano-framework.git
cd son-mano-framework
ansible-playbook install/mano.yml -e "docker_network_name=tango"
```
Dependencies for this installation are:

* Ansible > 2.4
* Docker > 17.12.0-ce
* Python3 Docker package > 3.4.1 (`pip3 install docker`)

At this point, you are running the MANO Framework locally, orchestrating on locally emulated resources. It is possible to orchestrate resources that are being managed by other virtual infrastructure managers (e.g. OpenStack, Kubernetes, etc.) if you replace the Emulator Wrapper with a dedicated wrapper for your VIM. Instructions on how to create such a wrapper can be found [here]().

To start using the standalone MANO Framework, you can use the `sonmano` Python3 library which consumes the MANO Framework API. You can install this library with

```bash
cd client
python3 setup.py install
```
Documentation for this library can be found [here]().

# Contributing

To contribute, go through these steps:

1. Fork [this repository](http://github.com/sonata-nfv/son-mano-framework);
2. Work on your proposed changes, preferably through submiting [issues](https://github.com/sonata-nfv/son-mano-framework/issues);
3. Push changes on your fork;
3. Submit a Pull Request;
4. Follow/answer related [issues](https://github.com/sonata-nfv/son-mano-framework/issues) (see Feedback-Channel, below).

# License

Son-mano-framework is published under Apache 2.0 license. Please see the LICENSE file for more details.

---
#### Lead Developers

The following lead developers are responsible for this repository and have admin rights. They can, for example, merge pull requests.

* Thomas Soenen (https://github.com/tsoenen)
* Manuel Peuster (https://github.com/mpeuster)
* Felipe Vicens (https://github.com/felipevicens)

#### Feedback-Channel

* [GitHub issues](https://github.com/sonata-nfv/son-mano-framework/issues)
