# SONATA's Specific Manager Registry plugin
Specific Manager Registry (SMR) is a special plugin that connects to the message broker and is responsible for managing the on-boarding and registration processes of Function-/Service-Specific Managers (FSMs/SSMs). 

## Requires
* Docker

## Implementation
* implemented in Python 3.4
* dependecies: amqp-storm
* The main implementation can be found in: `son-mano-specificmanager/son-mano-specific-manager-registry/son_mano_specific_manager_registry/specificmanagerregistry.py`

## How to run it

* (follow the general README.md of this repository to setup and test your environment)
* To run the SMR locally, you need:
 * a running RabbitMQ broker (see general README.md of this repo for info on how to do this)
 * a running plugin manager connected to the broker (see general README.md of this repo for info on how to do this)
 
* Run the SMR (directly in your terminal not in a Docker container):
 * `python3.4 son-mano-specificmanager/son-mano-specific-manager-registry/son_mano_specific_manager_registry/specificmanagerregistry.py`

* Or: run the SMR (in a Docker container):
 * (do in `son-mano-framework/`)
 * sudo docker build -t registry.sonata-nfv.eu:5 000/specificmanagerregistry -f son-mano-specificmanager/son-mano-specific-manager-registry/Dockerfile .
 * sudo docker run -it --rm --link broker:broker -v '/var/run/docker.sock:/var/run/docker.sock' --name specificmanagerregistry registry.sonata-nfv.eu:5000/specificmanagerregistry
 
## Output
The output of the SMR should look like this:
```
INFO:son-mano-specific-manager-registry-engine:Connected to Docker host: http+docker://localunixsocket
INFO:son-mano-base:plugin:Starting MANO Plugin: 'son-plugin.SpecificManagerRegistry' ...
DEBUG:son-mano-base:plugin:Waiting for registration (timeout=5) ...
INFO:son-mano-base:plugin:Plugin registered with UUID: '6e6df555-be44-444e-95a3-df51a5ac6e59'
DEBUG:son-mano-base:plugin:Received registration ok event.
DEBUG:son-mano-base:plugin:Received lifecycle.start event.
```


It shows how SMR connects to the broker and registers itself to the plugin manager.

## Unit tests

* To run the unit tests of the SMR individually, run the following from the root of the repo:
 * `./test/test_plugin-son-mano-smr.sh`
