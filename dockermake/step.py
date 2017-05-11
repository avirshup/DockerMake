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
from __future__ import print_function

import os, pprint
from io import StringIO, BytesIO

import sys

from . import utils, staging
DOCKER_TMPDIR = '_docker_make_tmp/'


class BuildStep(object):
    """ Stores and runs the instructions to build a single image.

    Args:
        imagename (str): name of this image definition
        baseimage (str): name of the image to inherit from (through "FROM")
        img_def (dict): yaml definition of this image
        buildname (str): what to call this image, once built
        bust_cache(bool): never use docker cache for this build step
    """

    def __init__(self, imagename, baseimage, img_def, buildname, bust_cache=False):
        self.imagename = imagename
        self.baseimage = baseimage
        self.dockerfile_lines = ['FROM %s\n' % baseimage,
                                 img_def.get('build', '')]
        self.buildname = buildname
        self.build_dir = img_def.get('build_directory', None)
        self.bust_cache = bust_cache
        self.sourcefile = img_def['_sourcefile']

    def build(self, client, pull=False, usecache=True):
        """
        Drives an individual build step. Build steps are separated by build_directory.
        If a build has zero one or less build_directories, it will be built in a single
        step.

        Args:
            client (docker.APIClient): docker client object that will build the image
            pull (bool): whether to pull dependent layers from remote repositories
            usecache (bool): whether to use cached layers or rebuild from scratch
        """
        print('     Image definition "%s" from file %s' % (self.imagename,
                                                           self.sourcefile))

        if self.bust_cache:
            usecache = False

        if not usecache:
            print('   INFO: Docker caching disabled - forcing rebuild')

        dockerfile = u'\n'.join(self.dockerfile_lines)

        build_args = dict(tag=self.buildname,
                          pull=pull,
                          nocache=not usecache,
                          decode=True, rm=True)

        if self.build_dir is not None:
            tempdir = self.write_dockerfile(dockerfile)
            build_args.update(fileobj=None,
                              path=os.path.abspath(os.path.expanduser(self.build_dir)),
                              dockerfile=os.path.join(DOCKER_TMPDIR, 'Dockerfile'))
        else:
            if sys.version_info.major == 2:
                build_args.update(fileobj=StringIO(dockerfile),
                                  path=None,
                                  dockerfile=None)
            else:
                build_args.update(fileobj=BytesIO(dockerfile.encode('utf-8')),
                                  path=None,
                                  dockerfile=None)

            tempdir = None

        # start the build
        stream = client.build(**build_args)
        try:
            utils.stream_docker_logs(stream, self.buildname)
        except ValueError as e:
            raise BuildError(dockerfile, e.args[0], build_args)

        # remove the temporary dockerfile
        if tempdir is not None:
            os.unlink(os.path.join(tempdir, 'Dockerfile'))
            os.rmdir(tempdir)

    def write_dockerfile(self, dockerfile):
        tempdir = os.path.abspath(os.path.join(self.build_dir, DOCKER_TMPDIR))
        temp_df = os.path.join(tempdir, 'Dockerfile')
        if not os.path.isdir(tempdir):
            os.makedirs(tempdir)
        with open(temp_df, 'w') as df_out:
            print(dockerfile, file=df_out)
        return tempdir


class FileCopyStep(BuildStep):
    """
    A specialized build step that copies files into an image from another image.

    Args:
        sourceimage (str): name of image to copy file from
        sourcepath (str): file path in source image
        base_image (str): name of image to copy file into
        destpath (str): directory to copy the file into
        buildname (str): name of the built image
        ymldef (Dict): yml definition of this build step
        definitionname (str): name of this definition
    """

    bust_cache = False  # can't bust this

    def __init__(self, sourceimage, sourcepath, base_image, destpath, buildname,
                 ymldef, definitionname):
        self.sourceimage = sourceimage
        self.sourcepath = sourcepath
        self.base_image = base_image
        self.destpath = destpath
        self.buildname = buildname
        self.definitionname = definitionname
        self.sourcefile = ymldef['_sourcefile']

    def build(self, client, pull=False, usecache=True):
        """
         Note:
            `pull` and `usecache` are for compatibility only. They're irrelevant because
            hey were applied when BUILDING self.sourceimage
        """
        print('     File copy from "%s", defined in file %s' % (self.definitionname, self.sourcefile))
        stage = staging.StagedFile(self.sourceimage, self.sourcepath, self.destpath)
        stage.stage(self.base_image, self.buildname)




class BuildError(Exception):
    def __init__(self, dockerfile, item, build_args):
        with open('dockerfile.fail', 'w') as dff:
            print(dockerfile, file=dff)
        with BytesIO() as stream:
            print('\n   -------- Docker daemon output --------', file=stream)
            pprint.pprint(item, stream, indent=4)
            print('   -------- Arguments to client.build --------', file=stream)
            pprint.pprint(build_args, stream, indent=4)
            print('This dockerfile was written to dockerfile.fail', file=stream)
            stream.seek(0)
            super(BuildError, self).__init__(stream.read())
