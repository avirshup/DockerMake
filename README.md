# DockerMake
Compose docker containers using human-readable YAML files.

Written by:<br>
<small>Aaron Virshup<br>
Bio/Nano Research Group<br>
Autodesk Research</small>

##### Requirements
You'll need python2.7, pyyaml, docker-py, and access to a docker daemon. If you have pip and a docker-machine, you can run these commands to get set up:
```bash
pip install pyyaml docker-py
eval $(docker-machine env [machine-name])
```

#### Example
There are 5 docker images to be built in this example. `devbase` is just basic compilation tools. `airline_data` adds a large CSV file to `devbase`. `python_image` installs some basic data science tools on top of `devbase`. `data_science` combines *both* `airline_data` and `python_image` to give you a docker image with both the data and the tools.

Here's the `DockerMake.yaml` file for this build:
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
  && apt-get install -y python python-pip \
  && pip install pandas
  
data_science:
 requires:
  - python_image
  - airline_data
```

To build an image called `alice/data_science`, you can run:
```bash
docker-make.py --user alice data_science
```
which will create an image with all the commands in `python_image` and `airline_data`.

This works by dynamically generating a new Dockerfile every time you ask to build something. However, most of the commands will be cached, especially if you have a large hierarchy of base images. This actually leads to _less_ rebuilding than if you had a series of Dockerfiles linked together with `FROM` commands.

#### Writing DockerMake.yaml
The idea is to write dockerfile commands for each specific piece of functionality in the `build` field, and "inherit" all other functionality from a list of other components that your image `requires`. If you need to add files with the ADD and COPY commands,  specify the root directory for those files with `build_directory`. Your tree of "requires" must have _exactly one_ unique named base image in the `FROM` field.
```yaml
[image_name]:
  build_directory: [relative path where the ADD and COPY commands will look for files]
  requires:
   - [other image name]
   - [yet another image name]
  FROM: [named_base_image]
  build: |
   RUN [something]
   ADD [something else]
   [Dockerfile commands go here]

[other image name]: ...
[yet another image name]: ...
```


### Command line usage 
```
usage: docker-make.py [-h] [--pull] [-f MAKEFILE] [-u USER] [-p] [-n] [-a]
                      [-l]
                      [TARGETS [TARGETS ...]]

NOTE: Docker environmental variables must be set. For a docker-machine, run
`eval $(docker-machine env [machine-name])`

positional arguments:
  TARGETS               Docker images to build as specified in the YAML file

optional arguments:
  -h, --help            show this help message and exit
  --pull                Pull updated external images
  -f MAKEFILE, --makefile MAKEFILE
                        YAML file containing build instructions
                        (default: DockerMake.yaml)
  -u USER, --user USER  Append this user tag to all built images, e.g.
                        `docker_make hello-world -u elvis` will tag the image
                        as `elvis/hello-world`
  -p, --print_dockerfiles
                        Print out the generated dockerfiles named
                        `Dockerfile.[image]`
  -n, --no_build        Only print Dockerfiles, don't build them. Implies
                        --print_dockerfiles.
  -a, --all             Print or build all dockerfiles in teh container
  -l, --list            List all available targets in the file, then exit.
```



Copyright (c) 2015, Autodesk Inc. Released under the simplified BSD license.
