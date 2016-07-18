# Docker-make
Build and manage stacks of docker images - a dependency graph for Dockerfiles
 
Table of Contents
=================
 * [What you can do with it](#what-you-can-do-with-it)
 * [Example](#example)
 * [Writing DockerMake\.yaml](#writing-dockermakeyaml)
 * [Requirements](#requirements)
 * [Command line usage](#command-line-usage)

### What you can do with it
 * Define small pieces of configuration or functionality, then mix them together into production docker images.
 * "Inherit" from multiple image builds
 * Easily manage images that pull files from multiple directories on your filesystem
 * Rebuild an entire stack of images as needed with a single command
 
**How is this different from docker-compose?**<br> `docker-make` automates and manages the process of building docker images. `docker-compose` spins up containers and links them to make serivces.

**How is this different from the FROM command in Dockerfiles?**
 1. Using the `requires` field, you can inherit from multiple images.
 2. You can create builds that reference multiple directories on your filesystem using the `build_directory` keyword.
 3. The builds are not tied to any image's tag or repository - when you build an image with `docker-make`, it will be up-to-date. 

### Example
[Click here to see a production-level example.](https://github.com/Autodesk/molecular-design-toolkit/blob/master/docker_images/DockerMake.yml)

This example builds a single docker image called `data_science`. It does this by mixing together three components: `devbase` (the base image), `airline_data` (a big CSV file), and `python_image` (a python installation). `docker-make` will create an image that combines all of these components.

Here's the `DockerMake.yml` file:
```yaml
devbase:
 FROM: phusion/baseimage
 build: |
  RUN apt-get -y update && apt-get -y install 
      build-essential 
   && mkdir -p /opt

airline_data:
 build_directory: sample_data/airline_data
 build: |
  ADD AirPassengers.csv /data

plant_data:
 build_directory: sample_data/plant_growth
 build: |
  ADD Puromycin.csv /data

python_image:
 requires:
  - devbase
 build: |
  RUN apt-get install -y python python-pandas

data_science:
 requires:
  - python_image
  - airline_data
  - plant_data

```

To build an image called `alice/data_science`, you can run:
```bash
docker-make.py data_science --repository alice
```
which will create an image with all the commands in `python_image` and `airline_data`.

This works by dynamically generating a new Dockerfile every time you ask to build something. However, most of the commands will be cached, especially if you have a large hierarchy of base images. This actually leads to _less_ rebuilding than if you had a series of Dockerfiles linked together with `FROM` commands.

Here's the dependency graph and generated Dockerfiles:

![dependency graph](img/step1.png)
![dockerfiles](img/step2.png)

### Writing DockerMake.yaml
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
Run `docker-make.py` from wherever you like. You'll need python2.7, pyyaml, docker-py, and access to a docker daemon. If you have pip and a docker-machine, you can run these commands to get set up:
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


Written by Aaron Virshup, Bio/Nano Research Group, Autodesk Research

Copyright (c) 2016, Autodesk Inc. Released under the simplified BSD license.
