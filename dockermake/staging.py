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

import docker.errors
from builtins import object

import os
import tempfile
import shutil

from . import utils

TMPDIR = tempfile.gettempdir()
BUILD_CACHEDIR = os.path.join(TMPDIR, 'dmk_cache')
BUILD_TEMPDIR = os.path.join(TMPDIR, 'dmk_download')


def clear_copy_cache():
    for path in (BUILD_CACHEDIR, BUILD_TEMPDIR):
        if os.path.exists(path):
            assert os.path.isdir(path), "'%s' is not a directory!"
            print('Removing docker-make cache %s' % path)
            shutil.rmtree(path)
        else:
            print('Cache directory %s does not exist.' % path)


class StagedFile(object):
    """ Tracks a file or directory that will be built in one image, then copied into others

    Args:
        sourceimage (str): name of the image to copy from
        sourcepath (str): path in the source image
        destpath (str): path in the target image
    """
    def __init__(self, sourceimage, sourcepath, destpath):
        self.sourceimage = sourceimage
        self.sourcepath = sourcepath
        self.destpath = destpath
        self._sourceobj = None
        self._cachedir = None

    def stage(self, startimage, newimage):
        """ Copies the file from source to target

        Args:
            startimage (str): name of the image to stage these files into
            newimage (str): name of the created image
        """
        from .step import BuildError

        client = utils.get_client()
        print(' * Copying FROM "%s:/%s" TO "%s://%s/"'%(self.sourceimage, self.sourcepath,
                                                        startimage, self.destpath))

        # copy build artifacts from the container if necessary
        cachedir = self._setcache(client)
        cacherelpath = os.path.relpath(cachedir, TMPDIR)
        if not os.path.exists(cachedir):
            print(' * Creating cache at %s' % cacherelpath)
            container = client.containers.create(self.sourceimage)
            try:
                tarfile_stream, tarfile_stats = container.get_archive(self.sourcepath)
            except docker.errors.NotFound:
                raise IOError('File "%s" does not exist in image "%s"!' %
                              (self.sourcepath, self.sourceimage))

            # write files to disk (would be nice to stream them, haven't gotten it to work)
            tempdir = tempfile.mkdtemp(dir=BUILD_TEMPDIR)
            with open(os.path.join(tempdir, 'content.tar'), 'wb') as localfile:
                for chunk in tarfile_stream.stream():
                    localfile.write(chunk)
            os.mkdir(cachedir)
            os.rename(tempdir, cachedir)
        else:
            print(' * Using cached files from %s' % cacherelpath)

        # write Dockerfile for the new image and then build it
        dockerfile = 'FROM %s\nADD content.tar %s' % (startimage, self.destpath)
        with open(os.path.join(cachedir, 'Dockerfile'), 'w') as df:
            df.write(dockerfile)

        buildargs = dict(path=cachedir,
                         tag=newimage,
                         decode=True)

        # Build and show logs
        stream = client.api.build(**buildargs)
        try:
            utils.stream_docker_logs(stream, newimage)
        except ValueError as e:
            raise BuildError(dockerfile, e.args[0], build_args=buildargs)

    def _setcache(self, client):
        if self._sourceobj is None:  # get image and set up cache if necessary

            self._sourceobj = client.images.get(self.sourceimage)

            if not os.path.exists(BUILD_CACHEDIR):
                os.mkdir(BUILD_CACHEDIR)

            if not os.path.exists(BUILD_TEMPDIR):
                os.mkdir(BUILD_TEMPDIR)

            image_cachedir = os.path.join(BUILD_CACHEDIR,
                                          self._sourceobj.id.replace('sha256:', ''))
            if not os.path.exists(image_cachedir):
                os.mkdir(image_cachedir)

            self._cachedir = os.path.join(image_cachedir,
                                          self.sourcepath.replace('/', '_-'))
            return self._cachedir

        else:  # make sure image ID hasn't changed
            assert self._sourceobj.id == client.images.get(self.sourceimage)
            return self._cachedir
