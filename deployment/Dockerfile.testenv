ARG PYVERSION=3.6
FROM python:${PYVERSION}-alpine

RUN apk add --no-cache curl git
ENV DOCKERVERSION=17.12.0-ce
RUN curl -fsSLO https://download.docker.com/linux/static/stable/x86_64/docker-${DOCKERVERSION}.tgz \
  && mv docker-${DOCKERVERSION}.tgz docker.tgz \
  && tar xzvf docker.tgz \
  && mv docker/docker /usr/local/bin \
  && rm -r docker docker.tgz

RUN pip install pytest
ADD test /opt/test
ADD example /opt/example