# Docker-make
Compose docker *images* using a dependency graph in a YAML file.

### What you can do with it
 * Define small pieces of configuration or functionality, then mix them together into production docker images.
 * Easily manage images that pull files from multiple directories on your filesystem
 * Rebuild an entire stack of images as needed with a single command
 * Assign tags, repositories, registries and pushes in batches as part of your build
 
**How is this different from docker-compose?** `docker-make` automates and manages the process of building docker images. `docker-compose` spins up containers and links them to make serivces.

### Example
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


#### Requirements
You'll need python2.7, pyyaml, docker-py, and access to a docker daemon. If you have pip and a docker-machine, you can run these commands to get set up:
```bash
pip install pyyaml docker-py
eval $(docker-machine env [machine-name])
```

### Command line usage 
```
usage: docker-make.py [-h] [-f MAKEFILE] [-a] [-l]
                      [--requires [REQUIRES [REQUIRES ...]]] [--name NAME]
                      [-p] [-n] [--pull] [--no-cache]
                      [--repository REPOSITORY] [--tag TAG]
                      [--push-to-registry] [--help-yaml]
                      [TARGETS [TARGETS ...]]

NOTE: Docker environmental variables must be set. For a docker-machine, run
`eval $(docker-machine env [machine-name])`

optional arguments:
  -h, --help            show this help message and exit

Choosing what to build:
  TARGETS               Docker images to build as specified in the YAML file
  -f MAKEFILE, --makefile MAKEFILE
                        YAML file containing build instructions
  -a, --all             Print or build all images (or those specified by
                        _ALL_)
  -l, --list            List all available targets in the file, then exit.
  --requires [REQUIRES [REQUIRES ...]]
                        Build a special image from these requirements.
                        Requires --name
  --name NAME           Name for custom docker images (requires --requires)

Dockerfiles:
  -p, --print_dockerfiles
                        Print out the generated dockerfiles named
                        `Dockerfile.[image]`
  -n, --no_build        Only print Dockerfiles, don't build them. Implies
                        --print.

Image caching:
  --pull                Always try to pull updated FROM images
  --no-cache            Rebuild every layer

Repositories and tags:
  --repository REPOSITORY, -r REPOSITORY, -u REPOSITORY
                        Prepend this repository to all built images, e.g.
                        `docker-make hello-world -u quay.io/elvis` will tag
                        the image as `quay.io/elvis/hello-world`. You can add
                        a ':' to the end to image names into tags: `docker-
                        make -u quay.io/elvis/repo: hello-world` will create
                        the image in the elvis repository: quay.io/elvis/repo
                        :hello-world
  --tag TAG, -t TAG     Tag all built images with this tag. If image names are
                        ALREADY tags (i.e., your repo name ends in a ":"),
                        this will append the tag name with a dash. For
                        example: `docker-make hello-world -u elvis/repo: -t
                        1.0` will create the image "elvis/repo:hello-world-1.0
  --push-to-registry, -P
                        Push all built images to the repository specified
                        (only if image repository contains a URL) -- to push
                        to dockerhub.com, use index.docker.io as the registry)

Help:
  --help-yaml           Print summary of YAML file format and exit.
```



Copyright (c) 2016, Autodesk Inc. Released under the simplified BSD license.
