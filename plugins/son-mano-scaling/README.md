# SONATA's service lifecycle manager plugin

## Requires
* Docker
* Python 3.4
* pika

## Implementation
* The main implementation can be found in: `son_mano_ssm_scaling/ssm_scaling.py`

## How to run it

* (follow the general README.md of this repository to setup and test your environment)
* To run the SSM locally, you need:
 * a running RabbitMQ broker
 * a running plugin manager connected to the broker
 
 
* Run a local broker (in a Docker container): 
 * (do in `son-mano-framework/`)
 * `docker build -t broker -f son-mano-broker/Dockerfile .`
 * `docker run -d -p 5672:5672 --name broker broker`
 
 
* Run the plugin manager (in a Docker container):
 * (do in `son-mano-framework/`)
 * `docker build -t pluginmanager -f son-mano-pluginmanager/Dockerfile .`
 * `docker run -it --link broker:broker --name pluginmanager pluginmanager`


* Run the SLM (directly in your terminal not in a Docker container):
 * `python plugins/son-mano-scaling/son_mano_ssm_scaling/ssm_scaling.py`


* Or: run the SLM (in a Docker container):
 * (do in `son-mano-framework/`)
 * `docker build -t ssm -f plugins/son-mano-scaling/Dockerfile .`
 * `docker run -it --link broker:broker --name ssm ssm`
 
 

