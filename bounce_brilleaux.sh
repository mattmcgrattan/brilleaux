#!/bin/bash

sudo docker kill brilleaux
sudo docker rm brilleaux

sudo docker run -d -p 9003:80 --name brilleaux \
  digirati/brilleaux:latest
