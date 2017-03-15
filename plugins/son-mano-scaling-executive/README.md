# SONATA's Scaling Executive
## Docker Build command
sudo docker build -t registry.sonata-nfv.eu:5000/scalingexecutive -f plugins/son-mano-scaling-executive/Dockerfile .
## Docker Run command
sudo docker run -it --rm --link broker:broker --name scalingexecutive registry.sonata-nfv.eu:5000/scalingexecutive