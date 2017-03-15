# SONATA's Placement Executive
## Docker Build command
sudo docker build -t registry.sonata-nfv.eu:5000/placementexecutive -f plugins/son-mano-placement-executive/Dockerfile .
## Docker Run command
sudo docker run -it --rm --link broker:broker --name placementexecutive registry.sonata-nfv.eu:5000/placementexecutive