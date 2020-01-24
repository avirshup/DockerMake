FROM python:3.8-alpine

RUN apk add --no-cache git build-base
ADD requirements.txt /tmp
RUN pip install -r /tmp/requirements.txt

ADD . /opt/DockerMake
WORKDIR /opt/DockerMake
RUN python setup.py sdist \
 && pip install dist/DockerMake*.tar.gz 

WORKDIR /opt
