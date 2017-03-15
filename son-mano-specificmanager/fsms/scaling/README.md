# Scaling Function Specific Manager.
## Docker Build command
sudo docker build -t sonfsmscaling1 -f son-mano-specificmanager/fsms/scaling/Dockerfile .
## Docker Run command
sudo docker run -it --rm --link broker:broker  --name sonfsmscaling1  sonfsmscaling1