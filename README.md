# son-mano-framework
SONATA's Service Platform MANO Framework


## Folder structure

* `plugins` contains MANO plugin implementations
* `son-mano-base` abstract plugin classes, helpers used by all plugins, ...
* `son-mano-broker` the message broker (start with a Dockerimage containing a default RabbitMQ installation)
* `son-mano-pluginmanager` the plugin manager component
* ... (there will be more)


## Run the PoC code locally (see below for simpler Docker Compose based execution)

### Requirements
* Running RabbitMQ broker instance on local machine (localhost)
* Python pika: `sudo pip install pika pytest`

### Run simple example:
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
4. request a list of active plugins from the plugin manager
5. de-register and stop itself after a few seconds

## Docker support
### Build Docker containers for each component

* `docker build -t broker -f son-mano-broker/Dockerfile .`
* `docker build -t pluginmanager -f son-mano-pluginmanager/Dockerfile .`
* `docker build -t exampleplugin -f plugins/son-mano-example-plugin-1/Dockerfile .`

### Run each component as a container

* `docker run -d -p 5672:5672 --name broker broker`
* `docker run -it --link broker:broker --name pluginmanager pluginmanager`
* `docker run -it --link broker:broker --name exampleplugin exampleplugin`


(using the hosts network stack is not optimal, but ok for now)

## Docker Compose support (should be used to deploy the platform)

Using [Docker Compose](https://docs.docker.com/compose/) allows us to deploy all components of the MANO framework in individual containers with a single command.

### Build (and Re-build)

* `docker-compose build`

### Start

* `docker-compose up`

### Stop (in second terminal)

* `docker-compose down`


## Unit tests

* Run tests using the following steps:
    * NOTICE: The tests need a running RabbitMQ broker to test the messaging subsystem! Without this, tests will fail.
    * `cd son-mano-framework`
    * `py.test -v`


## CI Integration (fully automated tests)

These tests are used by our CI/CD system and are fully automated. They spin up required support functions, e.g., the RabbitMQ broker in separated Docker containers and remove them after each test run.

* Test entrypoint scripts are located in: test/
* Trigger test execution from Jenkins: ```for i in `find ${WORKSPACE} -name test_*.sh -type f`; do $i; if [ $? -ne 0 ]; then exit 1; fi; done```
* Trigger test execution locally by hand: ```find -path "*test/*" -name "test_*.sh" -type f -execdir {} \;```
* This will start all components in independent Docker containers, run the tests, and cleanup everything
* Exitcode of each script is either 0 = test OK or 1 = test FAIL

