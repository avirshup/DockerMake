#!/usr/bin/env python2.7
"""
Multiple inheritance for your dockerfiles.
Requires: python 2.7, docker-py, pyyaml (RUN: easy_install pip; pip install docker-py pyyaml)

Copyright (c) 2015, Aaron Virshup. See LICENSE
"""
from collections import OrderedDict
from io import StringIO
import argparse

import docker,docker.utils
import yaml

class BuildStep(object):
    def __init__(self,baseimage):
        self.dockerfile = ['FROM %s\n'%baseimage]
        self.tag = None
        self.build_directory = None


class DockerMaker(object):
    def __init__(self, makefile, user=None,
                 build_images=True,
                 print_dockerfiles=False,
                 pull=False):
        if build_images:
            connection = docker.utils.kwargs_from_env()
            connection['tls'].assert_hostname = False
            self.client = docker.Client(**connection)
        else:
            self.client = None

        with open(makefile,'r') as yaml_file:
            self.img_defs = yaml.load(yaml_file)

        if user and user[-1] != '/':
            self.user = user + '/'
        else:
            self.user = ''
        self.build_images = build_images
        self.print_dockerfiles = print_dockerfiles
        self.pull = pull

    def build(self, image):
        """
        Drives the build of the final image - get the list of steps and execute them.
        :param image: name of the image from the yaml file to build
        :return: final tagged image name
        """
        print 'Starting build for %s'%image
        build_steps = self.generate_build_order(image)
        for step in build_steps:
            if self.build_images:
                dockerfile = StringIO(unicode('\n\n'.join(step.dockerfile)))
                if step.build_directory:
                    stream = self.client.build(path=step.build_directory,
                                               fileobj=dockerfile,
                                               tag=step.tag,
                                               pull=self.pull,
                                               decode=True)
                else:
                    stream = self.client.build(fileobj=dockerfile,
                                               tag=step.tag,
                                               pull=self.pull,
                                               decode=True)
                for item in stream: print item['stream'].strip()

            if self.print_dockerfiles:
                if '/' in step.tag: filename = 'Dockerfile.%s'%image
                else: filename = 'Dockerfile.%s'%step.tag

                with open(filename,'w') as dockerfile:
                    print >> dockerfile,'\n'.join(step.dockerfile)
        return step.tag

    def generate_build_order(self, image):
        """
        Separate the build into a series of one or more intermediate steps.
        Each specified build directory gets its own step
        """
        image_tag = self.user + image
        dependencies = self.sort_dependencies(image)
        base = self.get_external_base_image(dependencies, image)

        build_steps = [BuildStep(base)]
        step = build_steps[0]
        for d in dependencies:
            dep_definition = self.img_defs[d]
            mydir = dep_definition.get('build_directory', None)
            if mydir is not None:
                if step.build_directory is not None:
                    step.tag = '%dbuild_%s'%(len(build_steps),image)
                    build_steps.append(BuildStep(step.tag))
                    step = build_steps[-1]
                step.build_directory = mydir

            if 'build' in dep_definition:
                step.dockerfile.append('#Commands for %s'%d)
                step.dockerfile.append(dep_definition['build'])
            else:
                step.dockerfile.append('####end of requirements for %s'%d)

        #Sets the last step's name to the final build target
        step.tag = image_tag
        for step in build_steps:
            step.dockerfile.insert(0,'#Build directory: %s\n#tag: %s\n'%(step.build_directory,step.tag))
        return build_steps

    def sort_dependencies(self, com, dependencies=None):
        """
        Topologically sort the docker commands by their requirements
        TODO: make this sorting unique to take advantage of caching
        :param com: process this docker image's dependencies
        :param dependencies: running cache of sorted dependencies (ordered dict)
        :return type: OrderedDict
        """
        if dependencies is None: dependencies = OrderedDict()

        if com in dependencies: return
        requires = self.img_defs[com].get('requires', [])
        assert type(requires) == list,'Requirements for %s are not a list'%com

        for dep in requires:
            self.sort_dependencies(dep, dependencies)
        if com in dependencies:
            raise ValueError('Circular dependency found',dependencies)
        dependencies[com] = None
        return dependencies

    def get_external_base_image(self, dependencies, image):
        """
        Makes sure that this image has exactly one external base image
        """
        base = None
        base_for = None
        for d in dependencies:
            this_base = self.img_defs[d].get('FROM', None)
            if this_base is not None and base is not None and this_base != base:
                error = ('Multiple external dependencies: image %s depends on:\n' % image +
                         '  %s (FROM: %s), and\n' % (base_for, base) +
                         '  %s (FROM: %s).' % (d, this_base))
                raise ValueError(error)
            if this_base is not None:
                base = this_base
                base_for = d
        if base is None:
            raise ValueError("No base image found in %s's dependencies" % image)
        return base

def main():
    args = make_arg_parser().parse_args()
    maker = DockerMaker(args.makefile,user=args.user,
                        build_images=not (args.no_build or args.list),
                        print_dockerfiles=(args.print_dockerfiles or args.no_build),
                        pull=args.pull)

    if args.list:
        print 'TARGETS in `%s`'%args.makefile
        for item in maker.img_defs.keys(): print ' *',item
        return

    if args.all: targets = maker.img_defs.keys()
    else: targets = args.TARGETS

    for t in targets:
        name = maker.build(t)
        print 'Built:',name


def make_arg_parser():
    parser = argparse.ArgumentParser(description=
                                     "NOTE: Docker environmental variables must be set.\n"
                                     "For a docker-machine, run "
                                     "`eval $(docker-machine env [machine-name])`")
    parser.add_argument('TARGETS',nargs="*",
                        help='Docker images to build as specified in the YAML file')
    parser.add_argument('--pull',action='store_true',
                        help='Pull updated external images')
    parser.add_argument('-f','--makefile',
                        default='DockerMake.yaml',
                        help='YAML file containing build instructions')
    parser.add_argument('-u','--user',
                        help="Append this user tag to all built images, e.g.\n"
                             "`docker_make hello-world -u elvis` will tag the image as `elvis/hello-world`")
    parser.add_argument('-p','--print_dockerfiles',action='store_true',
                        help="Print out the generated dockerfiles named `Dockerfile.[image]`")
    parser.add_argument('-n','--no_build',action='store_true',
                        help='Only print Dockerfiles, don\'t build them. Implies --print.')
    parser.add_argument('-a','--all',action='store_true',
                        help="Print or build all dockerfiles in teh container")
    parser.add_argument('-l','--list',action='store_true',
                        help='List all available targets in the file, then exit.')
    return parser



__license__ = """Copyright (c) 2015, Aaron Virshup
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""

if __name__ == '__main__': main()
