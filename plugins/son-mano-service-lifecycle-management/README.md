# SONATA's service lifecycle manager plugin
Service Lifecycle Manager: Component in the SONATA framework that is responsible to manage the lifecycle of the deployed services.

## Requires
* Docker

## Implementation
* implemented in Python 3.4
* dependecies: amqp-storm
* The main implementation can be found in: `son_mano_slm/slm.py`

## How to run it

* (follow the general README.md of this repository to setup and test your environment)
* To run the SLM locally, you need:
 * a running RabbitMQ broker (see general README.md of this repo for info on how to do this)
 * a running plugin manager connected to the broker (see general README.md of this repo for info on how to do this)
 
* Run the SLM (directly in your terminal not in a Docker container):
 * `python3.4 plugins/son-mano-service-lifecycle-management/son_mano_slm/slm.py`

* Or: run the SLM (in a Docker container):
 * (do in `son-mano-framework/`)
 * `docker build -t slm -f plugins/son-mano-service-lifecycle-management/Dockerfile .`
 * `docker run -it --link broker:broker --name slm slm`
 
## Output
The output of the SLM should look like this:

```
INFO:son-mano-base:plugin:Starting MANO Plugin: 'son-plugin.ServiceLifecycleManager' ...
INFO:son-mano-base:messaging:Broker configuration found: '/etc/son-mano/broker.config'
INFO:son-mano-base:messaging:Connecting to RabbitMQ on 'amqp://guest:guest@broker:5672/%2F'...
INFO:son-mano-base:messaging:Creating a new channel...
INFO:son-mano-base:messaging:Declaring exchange 'son-kernel'...
INFO:son-mano-base:plugin:Plugin registered with UUID: '37afe090-cf56-484a-8242-7808f83f4b52'
INFO:plugin:slm:Lifecycle start event
```

It shows how the SLM connects to the broker, registers itself to the plugin manager and receives the lifecycle start event.

## Unit tests

* To run the unit tests of the SLM individually, run the following from the root of the repo:
 * `./test/test_plugin-son-mano-slm.sh`


