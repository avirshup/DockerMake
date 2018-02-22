FROM python:3.6-alpine

RUN apk add --no-cache git
ADD requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt pytest

ADD . /opt/DockerMake
WORKDIR /opt/DockerMake
RUN python setup.py sdist \
 && pip install dist/DockerMake*.tar.gz 

WORKDIR /opt
