# Task Service Specific Manager.
## Docker Build command
sudo docker build -t sonssmplacement1 -f son-mano-specificmanager/ssms/placement/Dockerfile .
## Docker Run command
sudo docker run -it --rm --link broker:broker  --name sonssmplacement1  sonssmplacement1