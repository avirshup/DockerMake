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
from future.utils import iteritems

import dockermake.step
from . import builds
from . import staging

RECOGNIZED_KEYS = set('requires build_directory build copy_from FROM description _sourcefile'
                      .split())
SPECIAL_FIELDS = set('_ALL_ _SOURCES_'.split())


class ImageDefs(object):
    """ Stores and processes the image definitions
    """
    def __init__(self, makefile_path):
        self._sources = set()
        self.makefile_path = makefile_path
        print('Working directory: %s' % os.path.abspath(os.curdir))
        print('Copy cache directory: %s' % staging.TMPDIR)
        self.ymldefs = self.parse_yaml(self.makefile_path)
        self.all_targets = self.ymldefs.pop('_ALL_', None)

    def parse_yaml(self, filename):
        fname = os.path.expanduser(filename)
        print('READING %s' % os.path.expanduser(fname))
        if fname in self._sources:
            raise ValueError('Circular _SOURCES_')
        self._sources.add(fname)

        with open(fname, 'r') as yaml_file:
            yamldefs = yaml.load(yaml_file)

        self._fix_file_paths(filename, yamldefs)

        sourcedefs = {}
        for s in yamldefs.get('_SOURCES_', []):
            src = self.parse_yaml(s)
            sourcedefs.update(src)

        sourcedefs.update(yamldefs)
        return sourcedefs

    @staticmethod
    def _fix_file_paths(ymlfilepath, yamldefs):
        """ Interpret all paths relative the the current yaml file
        """
        pathroot = os.path.dirname(ymlfilepath)

        for field, item in iteritems(yamldefs):
            if field == '_SOURCES_':
                yamldefs['_SOURCES_'] = [os.path.relpath(_get_abspath(pathroot, p))
                                         for p in yamldefs['_SOURCES_']]
                continue
            elif field in SPECIAL_FIELDS:
                continue
            elif 'build_directory' in item:
                item['build_directory'] = _get_abspath(pathroot, item['build_directory'])

            # save the file path for logging
            f = os.path.relpath(ymlfilepath)
            if '/' not in f:
                f = './%s' % f
            item['_sourcefile'] = f

            for key in item:
                if key not in RECOGNIZED_KEYS:
                    raise KeyError('Field "%s" in image "%s" not recognized' %
                                   (key, field))

    def generate_build(self, image, targetname, rebuilds=None):
        """
        Separate the build into a series of one or more intermediate steps.
        Each specified build directory gets its own step

        Args:
            image (str): name of the image as defined in the dockermake.py file
            targetname (str): name to tag the final built image with
            rebuilds (List[str]): list of image layers to rebuild (i.e., without docker's cache)
        """
        from_image = self.get_external_base_image(image)
        build_steps = []
        istep = 0
        sourceimages = set()
        if rebuilds is None:
            rebuilds = []
        else:
            rebuilds = set(rebuilds)

        base_image = from_image
        for base_name in self.sort_dependencies(image):
            istep += 1
            buildname = 'dmkbuild_%s_%d' % (image, istep)
            build_steps.append(dockermake.step.BuildStep(base_name,
                                                         base_image,
                                                         self.ymldefs[base_name],
                                                         buildname,
                                                         bust_cache=base_name in rebuilds))
            base_image = buildname

            for sourceimage, files in iteritems(self.ymldefs[base_name].get('copy_from', {})):
                sourceimages.add(sourceimage)
                for sourcepath, destpath in iteritems(files):
                    istep += 1
                    buildname = 'dmkbuild_%s_%d' % (image, istep)
                    build_steps.append(dockermake.step.FileCopyStep(sourceimage, sourcepath,
                                                                    base_image, destpath,
                                                                    buildname,
                                                                    self.ymldefs[base_name],
                                                                    base_name))
                    base_image = buildname

        sourcebuilds = [self.generate_build(img, img) for img in sourceimages]

        return builds.BuildTarget(imagename=image,
                                  targetname=targetname,
                                  steps=build_steps,
                                  sourcebuilds=sourcebuilds,
                                  from_image=from_image)

    def sort_dependencies(self, image, dependencies=None):
        """
        Topologically sort the docker commands by their requirements

        Args:
           image (str): process this docker image's dependencies
           dependencies (OrderedDict): running cache of sorted dependencies (ordered dict)

        Returns:
            List[str]: list of dependencies a topologically-sorted build order
        """
        if dependencies is None:
            dependencies = OrderedDict()  # using this as an ordered set - not storing any values

        if image in dependencies:
            return

        requires = self.ymldefs[image].get('requires', [])
        assert type(requires) == list, 'Requirements for %s are not a list' % image

        for dep in requires:
            self.sort_dependencies(dep, dependencies)
        if image in dependencies:
            raise ValueError('Circular dependency found', dependencies)
        dependencies[image] = None
        return dependencies.keys()

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


def _get_abspath(pathroot, relpath):
    path = os.path.expanduser(pathroot)
    buildpath = os.path.expanduser(relpath)

    if not os.path.isabs(buildpath):
        buildpath = os.path.join(os.path.abspath(path), buildpath)

    return buildpath


