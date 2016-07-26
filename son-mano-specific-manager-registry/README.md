# SONATA's Specific Manager Registry plugin
Specific Manager Registry (SMR) is a special plugin that connects to the message broker and is responsible for managing the on-boarding and registration processes of Function-/Service-Specific Managers (FSMs/SSMs). 

## Requires
* Docker

## Implementation
* implemented in Python 3.4
* dependecies: amqp-storm
* The main implementation can be found in: `son_mano_specific_manager_registry/specificmanagerregistry.py`

## How to run it

* (follow the general README.md of this repository to setup and test your environment)
* To run the SMR locally, you need:
 * a running RabbitMQ broker (see general README.md of this repo for info on how to do this)
 * a running plugin manager connected to the broker (see general README.md of this repo for info on how to do this)
 
* Run the SMR (directly in your terminal not in a Docker container):
 * `python3.4 son-mano-specific-manager-registry/son_mano_specific_manager_registry/specificmanagerregistry.py`

* Or: run the SMR (in a Docker container):
 * (do in `son-mano-framework/`)
 * `docker build -t registry.sonata-nfv.eu:5000/specificmanagerregistry -f son-mano-specific-manager-registry/Dockerfile .`
 * `docker run -it -rm -v '/var/run/docker.sock:/var/run/docker.sock' --link broker:broker --name smr registry.sonata-nfv.eu:5000/specificmanagerregistry`
 
## Output
The output of the SMR should look like this:
```
WARNING:son-mano-specific-manager-registry-engine:ENV variable 'DOCKER_HOST' not set. Using 'unix://var/run/docker.sock' as fallback.
INFO:son-mano-specific-manager-registry-engine:Connected to Docker host: 'http+docker://localunixsocket'
INFO:son-mano-base:plugin:Starting MANO Plugin: 'smr.SpecificManagerRegistry' ...
DEBUG:son-mano-base:plugin:Waiting for registration (timeout=5) ...
INFO:son-mano-base:plugin:Plugin registered with UUID: 'ab7219d6-07f1-422a-90da-73992e56197f'
DEBUG:son-mano-base:plugin:Received registration ok event.
```


It shows how the SMR connects to the broker and registers itself to the plugin manager.

## Unit tests

* To run the unit tests of the SMR individually, run the following from the root of the repo:
 * `./test/test_plugin-son-mano-smr.sh`
