#!/usr/bin/env python2.7
# Copyright 2016 Autodesk Inc.
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

from __future__ import print_function
from builtins import object

import os
from collections import OrderedDict
import yaml

from . import builds


class ImageDefs(object):
    """ Stores and processes the image definitions
    """
    def __init__(self, makefile_path):
        self._sources = set()
        self.makefile_path = makefile_path
        self.ymldefs = self.parse_yaml(self.makefile_path)
        self.all_targets = self.ymldefs.pop('_ALL_', None)

    def parse_yaml(self, filename):
        fname = os.path.expanduser(filename)
        print('READING %s' % os.path.expanduser(fname))
        if fname in self._sources:
            raise ValueError('Circular _SOURCE_')
        self._sources.add(fname)

        with open(fname, 'r') as yaml_file:
            yamldefs = yaml.load(yaml_file)

        # Interpret build directory paths relative to this DockerMake.yml file
        for item in yamldefs.values():
            _fix_build_path(item, os.path.dirname(fname))

        sourcedefs = {}
        for s in yamldefs.get('_SOURCES_', []):
            src = self.parse_yaml(s)
            sourcedefs.update(src)

        sourcedefs.update(yamldefs)
        return sourcedefs

    def generate_build(self, image, targetname):
        """
        Separate the build into a series of one or more intermediate steps.
        Each specified build directory gets its own step

        Args:
            image (str): name of the image as defined in the dockermake.py file
            targetname (str): name to tag the final built image with
        """
        base_image = self.get_external_base_image(image)
        build_steps = []
        istep = 0
        sourceimages = set()

        for base_name in self.sort_dependencies(image):
            istep += 1
            buildname = 'dmkbuild_%s_%d' % (image, istep)
            build_steps.append(builds.BuildStep(base_name,
                                                base_image,
                                                self.ymldefs[base_name],
                                                buildname))
            base_image = buildname

            for sourceimage, files in self.ymldefs[base_name].get('built_files', {}).iteritems():
                sourceimages.add(sourceimage)
                for sourcepath, destpath in files.iteritems():
                    istep += 1
                    buildname = 'dmkbuild_%s_%d' % (image, istep)
                    build_steps.append(builds.FileCopyStep(sourceimage, sourcepath,
                                                           base_image, destpath,
                                                           buildname))
                    base_image = buildname

        sourcebuilds = [self.generate_build(img, img) for img in sourceimages]

        return builds.BuildTarget(imagename=image,
                                  targetname=targetname,
                                  steps=build_steps,
                                  sourcebuilds=sourcebuilds)

    def sort_dependencies(self, image, dependencies=None):
        """
        Topologically sort the docker commands by their requirements

        Args:
           image (str): process this docker image's dependencies
           dependencies (OrderedDict): running cache of sorted dependencies (ordered dict)

        Returns:
            OrderedDict: dictionary of this image's requirements
        """
        if dependencies is None:
            dependencies = OrderedDict()

        if image in dependencies:
            return

        requires = self.ymldefs[image].get('requires', [])
        assert type(requires) == list, 'Requirements for %s are not a list' % image

        for dep in requires:
            self.sort_dependencies(dep, dependencies)
        if image in dependencies:
            raise ValueError('Circular dependency found', dependencies)
        dependencies[image] = None
        return dependencies

    def get_external_base_image(self, image):
        """ Makes sure that this image has exactly one external base image
        """
        externalbase = self.ymldefs[image].get('FROM', None)

        for base in self.ymldefs[image].get('requires', []):
            try:
                otherexternal = self.get_external_base_image(base)
            except ValueError:
                continue

            if externalbase is None:
                externalbase = otherexternal
            elif otherexternal is None:
                continue
            elif externalbase != otherexternal:
                error = ('Multiple external dependencies: depends on:\n' % image +
                         '  %s (FROM: %s), and\n' % (image, externalbase) +
                         '  %s (FROM: %s).' % (base, otherexternal))
                raise ValueError(error)

        if not externalbase:
            raise ValueError("No base image found in %s's dependencies" % image)
        return externalbase


def _fix_build_path(item, filepath):
    path = os.path.expanduser(filepath)

    if 'build_directory' not in item:
        return
    elif os.path.isabs(item['build_directory']):
        return
    else:
        item['build_directory'] = os.path.join(os.path.abspath(path),
                                               item['build_directory'])


