#Dumb Function Specific Manager.
## Docker Build command
sudo docker build -t sonfsmscaling1 -f son-mano-specificmanager/fsms/dumb/Dockerfile .
## Docker Run command
sudo docker run -it --rm --link broker:broker  --name sonfsmdumb1  sonfsmscaling1
