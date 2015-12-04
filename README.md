# DockerMake
Compose docker containers using human-readable YAML files.

To use it, you'll need to run:
```bash
pip install pyyaml docker-py
eval $(docker-machine env [machine-name])
```

Sample DockerMake.yaml:
```yaml
devbase:
 FROM: phusion/baseimage
 build: |
  RUN apt-get -y update && apt-get -y install build-essential

airline_data:
 requires:
  - devbase
 build_directory: sample_data/airline_data
 build: |
  ADD AirlinePassengers.csv
  
python_image:
 requires:
  - devbase
 build: |
  RUN apt-get -y update \
  && apt-get install -y python python-pip
  && pip install pandas
  
data_science:
 requires:
  - python_image
  - airline_data
```

HELP:
```bash
usage: docker-make.py [-h] [-f MAKEFILE] [-u USER] [-p] [-n] [-a] [-l]
                      [TARGETS [TARGETS ...]]

NOTE: Docker environmental variables must be set. For a docker-machine, run
`eval $(docker-machine env [machine-name])`

positional arguments:
  TARGETS               Docker images to build as specified in the YAML file

optional arguments:
  -h, --help            show this help message and exit
  -f MAKEFILE, --makefile MAKEFILE
                        YAML file containing build instructions (default: DockerMake.yaml)
  -u USER, --user USER  Append this user tag to all built images, e.g.
                        `docker_make hello-world -u elvis` will tag the image
                        as `elvis/hello-world`
  -p, --print_dockerfiles
                        Print out the generated dockerfiles named
                        `Dockerfile.[image]`
  -n, --no_build        Only print Dockerfiles, don't build them. Implies
                        --print.
  -a, --all             Print or build all dockerfiles in teh container
  -l, --list            List all available targets in the file, then exit.
```
