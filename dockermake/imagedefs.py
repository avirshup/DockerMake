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
import uuid
from future.utils import iteritems

import dockermake.step
from . import builds
from . import staging
from . import errors
from . import utils

RECOGNIZED_KEYS = set(('requires build_directory build copy_from FROM description _sourcefile'
                       ' FROM_DOCKERFILE ignore ignorefile')
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
        try:
            self.ymldefs = self.parse_yaml(self.makefile_path)
        except errors.UserException:
            raise
        except Exception as exc:
            raise errors.ParsingFailure('Failed to read file %s:\n' % self.makefile_path +
                                        str(exc))
        self.all_targets = self.ymldefs.pop('_ALL_', [])
        self._external_dockerfiles = {}

    def parse_yaml(self, filename):
        fname = os.path.expanduser(filename)
        print('READING %s' % os.path.expanduser(fname))
        if fname in self._sources:
            raise errors.CircularSourcesError('Circular _SOURCES_ in %s' % self.makefile_path)
        self._sources.add(fname)

        with open(fname, 'r') as yaml_file:
            yamldefs = yaml.load(yaml_file)

        self._check_yaml_and_paths(filename, yamldefs)

        sourcedefs = {}
        for s in yamldefs.get('_SOURCES_', []):
            src = self.parse_yaml(s)
            sourcedefs.update(src)

        sourcedefs.update(yamldefs)
        return sourcedefs

    @staticmethod
    def _check_yaml_and_paths(ymlfilepath, yamldefs):
        """ Checks YAML for errors and resolves all paths
        """
        relpath = os.path.relpath(ymlfilepath)
        if '/' not in relpath:
            relpath = './%s' % relpath
        pathroot = os.path.abspath(os.path.dirname(ymlfilepath))

        for imagename, defn in iteritems(yamldefs):
            if imagename == '_SOURCES_':
                yamldefs['_SOURCES_'] = [os.path.relpath(_get_abspath(pathroot, p))
                                         for p in yamldefs['_SOURCES_']]
                continue
            elif imagename in SPECIAL_FIELDS:
                continue

            for key in ('build_directory', 'FROM_DOCKERFILE', 'ignorefile'):
                if key in defn:
                    defn[key] = _get_abspath(pathroot, defn[key])

            if 'copy_from' in defn:
                if not isinstance(defn['copy_from'], dict):
                    raise errors.ParsingFailure((
                            'Syntax error in file "%s": \n' +
                            'The "copy_from" field in image definition "%s" is not \n' 
                            'a key:value list.') % (ymlfilepath, imagename))
                for otherimg, value in defn.get('copy_from', {}).items():
                    if not isinstance(value, dict):
                        raise errors.ParsingFailure((
                            'Syntax error in field:\n'
                            '     %s . copy_from . %s\nin file "%s". \n'
                            'All entries must be of the form "sourcepath: destpath"')%
                                 (imagename, otherimg, ymlfilepath))

            # save the file path for logging
            defn['_sourcefile'] = relpath

            if 'ignore' in defn and 'ignorefile' in defn:
                raise errors.MultipleIgnoreError(
                        'Image "%s" has both "ignore" AND "ignorefile" fields.' % imagename +
                        ' At most ONE of these should be defined')

            for key in defn:
                if key not in RECOGNIZED_KEYS:
                    raise errors.UnrecognizedKeyError(
                            'Field "%s" in image "%s" in file "%s" not recognized' %
                            (key, imagename, relpath))

    def generate_build(self, image, targetname, rebuilds=None, cache_repo='', cache_tag=''):
        """
        Separate the build into a series of one or more intermediate steps.
        Each specified build directory gets its own step

        Args:
            image (str): name of the image as defined in the dockermake.py file
            targetname (str): name to tag the final built image with
            rebuilds (List[str]): list of image layers to rebuild (i.e., without docker's cache)
            cache_repo (str): repository to get images for caches in builds
            cache_tag (str): tags to use from repository for caches in builds
        """
        from_image = self.get_external_base_image(image)
        if cache_repo or cache_tag:
            cache_from = utils.generate_name(image, cache_repo, cache_tag)
        else:
            cache_from = None
        if from_image is None:
            raise errors.NoBaseError("No base image found in %s's dependencies" % image)
        if isinstance(from_image, ExternalDockerfile):
            build_first = from_image
            base_image = from_image.tag
        else:
            base_image = from_image
            build_first = None
        build_steps = []
        istep = 0
        sourceimages = set()
        if rebuilds is None:
            rebuilds = []
        else:
            rebuilds = set(rebuilds)

        for base_name in self.sort_dependencies(image):
            istep += 1
            buildname = 'dmkbuild_%s_%d' % (image, istep)
            build_steps.append(
                    dockermake.step.BuildStep(
                            base_name, base_image, self.ymldefs[base_name],
                            buildname, bust_cache=base_name in rebuilds,
                            build_first=build_first, cache_from=cache_from))

            base_image = buildname
            build_first = None

            for sourceimage, files in iteritems(self.ymldefs[base_name].get('copy_from', {})):
                sourceimages.add(sourceimage)
                for sourcepath, destpath in iteritems(files):
                    istep += 1
                    buildname = 'dmkbuild_%s_%d' % (image, istep)
                    build_steps.append(
                            dockermake.step.FileCopyStep(
                                    sourceimage, sourcepath, destpath,
                                    base_name, base_image, self.ymldefs[base_name],
                                    buildname, bust_cache=base_name in rebuilds,
                                    build_first=build_first, cache_from=cache_from))
                    base_image = buildname

        sourcebuilds = [self.generate_build(img, img, cache_repo=cache_repo, cache_tag=cache_tag)
                        for img in sourceimages]

        return builds.BuildTarget(imagename=image,
                                  targetname=targetname,
                                  steps=build_steps,
                                  sourcebuilds=sourcebuilds,
                                  from_image=from_image)

    def sort_dependencies(self, image, dependencies=None):
        """
        Topologically sort the docker commands by their requirements

        Note:
            Circular "requires" dependencies are assumed to have already been checked in
            get_external_base_image, they are not checked here

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

        for dep in requires:
            self.sort_dependencies(dep, dependencies)

        dependencies[image] = None
        return dependencies.keys()

    def get_external_base_image(self, image, stack=None):
        """ Makes sure that this image has exactly one external base image
        """
        if stack is None:
            stack = list()

        mydef = self.ymldefs[image]

        if image in stack:
            stack.append(image)
            raise errors.CircularDependencyError('Circular dependency found:\n' + '->'.join(stack))
        stack.append(image)

        # Deal with FROM and FROM_DOCKERFILE fields
        if 'FROM' in mydef and 'FROM_DOCKERFILE' in mydef:
            raise errors.MultipleBaseError(
                    'ERROR: Image "%s" has both a "FROM" and a "FROM_DOCKERFILE" field.' % image +
                    '       It should have at most ONE of these fields.')
        if 'FROM' in mydef:
            externalbase = mydef['FROM']
        elif 'FROM_DOCKERFILE' in mydef:
            path = mydef['FROM_DOCKERFILE']
            if path not in self._external_dockerfiles:
                self._external_dockerfiles[path] = ExternalDockerfile(path)
            externalbase = self._external_dockerfiles[path]
        else:
            externalbase = None

        requires = mydef.get('requires', [])
        if not isinstance(requires, list):
            raise errors.InvalidRequiresList('Requirements for image "%s" are not a list' % image)

        for base in requires:
            try:
                otherexternal = self.get_external_base_image(base, stack)
            except ValueError:
                continue

            if externalbase is None:
                externalbase = otherexternal
            elif otherexternal is None:
                continue
            elif externalbase != otherexternal:
                raise errors.ConflictingBaseError(
                        'Multiple external dependencies: definition "%s" depends on:\n' % image +
                        '  %s (FROM: %s), and\n' % (image, externalbase) +
                        '  %s (FROM: %s).' % (base, otherexternal))

        assert stack.pop() == image
        return externalbase


class ExternalDockerfile(object):
    def __init__(self, path):
        self.path = path
        self.built = False
        self.tag = uuid.uuid4()

    def __str__(self):
        return "Dockerfile at %s" % self.path

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        else:
            return self.path == other.path


def _get_abspath(pathroot, relpath):
    path = os.path.expanduser(pathroot)
    buildpath = os.path.expanduser(relpath)

    if not os.path.isabs(buildpath):
        buildpath = os.path.join(os.path.abspath(path), buildpath)

    return buildpath


