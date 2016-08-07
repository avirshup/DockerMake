FROM gliderlabs/alpine:3.3

RUN apk add --update \
    python \
    python-dev \
    py-pip \
    build-base \
  && pip install virtualenv \
  && rm -rf /var/cache/apk/*

RUN pip install pyyaml docker-py

ADD ./docker-make.py /usr/local/bin/docker-make.py

WORKDIR "/data"
ENTRYPOINT ["/usr/local/bin/docker-make.py"]
