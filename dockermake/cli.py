from __future__ import print_function
# Copyright 2015-2017 Autodesk Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import argparse
import textwrap


def make_arg_parser():
    parser = argparse.ArgumentParser(description=
                                     "NOTE: Docker environmental variables must be set.\n"
                                     "For a docker-machine, run "
                                     "`eval $(docker-machine env [machine-name])`")
    bo = parser.add_argument_group('Choosing what to build')
    bo.add_argument('TARGETS', nargs="*",
                    help='Docker images to build as specified in the YAML file')
    bo.add_argument('-f', '--makefile',
                    default='DockerMake.yml',
                    help='YAML file containing build instructions')
    bo.add_argument('-a', '--all', action='store_true',
                    help="Print or build all images (or those specified by _ALL_)")
    bo.add_argument('-l', '--list', action='store_true',
                    help='List all available targets in the file, then exit.')
    bo.add_argument('--requires', nargs="*",
                    help='Build a special image from these requirements. Requires --name')
    bo.add_argument('--name', type=str,
                    help="Name for custom docker images (requires --requires)")

    df = parser.add_argument_group('Dockerfiles')
    df.add_argument('-p', '--print-dockerfiles', '--print_dockerfiles', action='store_true',
                    help="Print out the generated dockerfiles named `Dockerfile.[image]`")
    df.add_argument('-n', '--no_build', action='store_true',
                    help='Only print Dockerfiles, don\'t build them. Implies --print.')
    df.add_argument('--dockerfile-dir', default='docker_makefiles',
                    help='Directory to save dockerfiles in (default: ./docker_makefiles)')

    ca = parser.add_argument_group('Image caching')
    ca.add_argument('--pull', action='store_true',
                    help='Always try to pull updated FROM images')
    ca.add_argument('--no-cache', action='store_true',
                    help="Rebuild every layer")
    ca.add_argument('--bust-cache', action='append',
                    help='Force docker to rebuilt all layers in this image. You can bust '
                    'multiple image layers by passing --bust-cache multiple times.')
    ca.add_argument('--clear-copy-cache', '--clear-cache', action='store_true',
                    help="Remove docker-make's cache of files for `copy-from`.")

    rt = parser.add_argument_group('Repositories and tags')
    rt.add_argument('--repository', '-r', '-u',
                    help="Prepend this repository to all built images, e.g.\n"
                         "`docker-make hello-world -u quay.io/elvis` will tag the image "
                         "as `quay.io/elvis/hello-world`. You can add a ':' to the end to "
                         "image names into tags:\n `docker-make -u quay.io/elvis/repo: hello-world` "
                         "will create the image in the elvis repository: quay.io/elvis/repo:hello-world")
    rt.add_argument('--tag', '-t', type=str,
                    help='Tag all built images with this tag. If image names are ALREADY tags (i.e.,'
                         ' your repo name ends in a ":"), this will append the tag name with a dash. '
                         'For example: `docker-make hello-world -u elvis/repo: -t 1.0` will create '
                         'the image "elvis/repo:hello-world-1.0')
    rt.add_argument('--push-to-registry', '-P', action='store_true',
                    help='Push all built images to the repository specified '
                         '(only if image repository contains a URL) -- to push to dockerhub.com, '
                         'use index.docker.io as the registry)')
    rt.add_argument('--registry-user', '--user',
                    help='For pushes: log into the registry using this username')
    rt.add_argument('--registry-token', '--token',
                    help='Token or password to log into registry (optional; uses $HOME/.dockercfg '
                         'or $HOME/.docker/config.json if not passed)')

    hh = parser.add_argument_group('Help')
    hh.add_argument('--version', action='store_true',
                    help="Print version and exit.")
    hh.add_argument('--help-yaml', action='store_true',
                    help="Print summary of YAML file format and exit.")

    return parser


def print_yaml_help():
    print("A brief introduction to writing Dockerfile.yml files:\n")

    print('SYNTAX:')
    print(printable_code("""[image_name]:
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
[yet another image name]: ..."""))

    print()
    print(textwrap.fill("The idea is to write dockerfile commands for each specific "
                        'piece of functionality in the build field, and "inherit" all other'
                        ' functionality from a list of other components that your image requires. '
                        'If you need to add files with the ADD and COPY commands, specify the root'
                        ' directory for those files with build_directory. Your tree of '
                        '"requires" must have exactly one unique named base image '
                        'in the FROM field.'))

    print('\n\nAN EXAMPLE:')
    print(printable_code("""devbase:
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
  - airline_data"""))


def printable_code(c):
    output = []
    dedented = textwrap.dedent(c)
    for line in dedented.split('\n'):
        output.append(' >> ' + line)
    return '\n'.join(output)

