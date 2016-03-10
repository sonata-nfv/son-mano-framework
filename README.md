[![Build Status](http://jenkins.sonata-nfv.eu/buildStatus/icon?job=son-mano-framework)](http://jenkins.sonata-nfv.eu/job/son-mano-framework)

# son-mano-framework
## SONATA's Service Platform MANO Framework

This repository contains the orchestration core (the flexible MANO framework) and all its components (broker, plugins, ...).

## Lead Developers
The following lead developers are responsible for this repository and have admin rights. They can, for example, merge pull requests.

* Sharon Mendel-Brin (smendel) 
* Manuel Peuster (mpeuster)
* Felipe Vicens (felipevicens)

## Dependencies
* Docker
* docker-compose
* RabbitMQ
* pika
* pytest
* pytest-runner

## Folder structure

* `libs/` contains any supporting libraries
* `plugins/` contains MANO plugin implementations
* `son-mano-base/` abstract base classes for plugins, messaging support
* `son-mano-broker/` the message broker (a Dockerimage containing a default RabbitMQ installation)
* `son-mano-pluginmanager/` the plugin manager component
* `test/` entry points (bash scripts) to trigger tests of sub-components (e.g., for CI/CD)
* `utils/` helper functionality, scripts, tools


## Run MANO framework

(see below for simpler Docker Compose based execution)


### Run directly:

* Requires a locally running RabbitMQ instance
* Do a `python setup.py develop` for each component


* Terminal 1: Run the plugin manager component
 * `cd son-mano-pluginmanager/sonmanopluginmanager/`
 * `python __main__.py`

* Terminal 2: Run the example plugin
 * `cd plugins/son-mano-example-plugin-1/sonmanoexampleplugin1/`
 * `python __main__.py`

What will happen? The example plugin will ...

1. connect to the broker
2. register itself to the plugin manager
3. periodically send heartbeat messages to the plugin manager
4. plugin manager will broadcast plugin status information whenever it changes
5. de-register and stop itself after a few seconds

### Docker support
#### Build Docker containers for each component

* `docker build -t broker -f son-mano-broker/Dockerfile .`
* `docker build -t pluginmanager -f son-mano-pluginmanager/Dockerfile .`
* `docker build -t exampleplugin -f plugins/son-mano-example-plugin-1/Dockerfile .`

#### Run each component as a container

* `docker run -d -p 5672:5672 --name broker broker`
* `docker run -it --link broker:broker --name pluginmanager pluginmanager`
* `docker run -it --link broker:broker --name exampleplugin exampleplugin`


### Docker Compose support (should be used to deploy the platform)

Using [Docker Compose](https://docs.docker.com/compose/) allows us to deploy all components of the MANO framework in individual containers with a single command.

#### Build (and Re-build)

* `docker-compose build`

#### Start

* `docker-compose up`

#### Stop (in second terminal)

* `docker-compose down`


## Test

### General

* ```./run_tests.sh```

### Python unit tests

* Run tests using the following steps:
    * NOTICE: The tests need a running RabbitMQ broker to test the messaging subsystem! Without this, tests will fail.
    * `cd son-mano-framework`
    * `py.test -v`


### CI Integration (fully automated tests)

These tests are used by our CI/CD system and are fully automated. They spin up required support functions, e.g., the RabbitMQ broker in separated Docker containers and remove them after each test run.

* Test entrypoint scripts are located in: test/
* Trigger test execution from Jenkins: ```for i in `find ${WORKSPACE} -name test_*.sh -type f`; do $i; if [ $? -ne 0 ]; then exit 1; fi; done```
* Trigger test execution locally by hand (does the same like Jenkins does): ```./run_tests.sh```
* This will start all components in independent Docker containers, run the tests, and cleanup everything
* Exitcode of each script is either 0 = test OK or 1 = test FAIL

