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

import os
import pprint
from io import BytesIO, StringIO

from builtins import object
from builtins import str

DOCKER_TMPDIR = '_docker_make_tmp/'


class BuildStep(object):
    """ Stores and runs the instructions to build a single image.

    Args:
        imagename (str): name of this image definition
        baseimage (str): name of the image to inherit from (through "FROM")
        img_def (dict): yaml definition of this image
        buildname (str): what to call this image, once built
    """

    def __init__(self, imagename, baseimage, img_def, buildname):
        self.imagename = imagename
        self.baseimage = baseimage
        self.dockerfile_lines = ['FROM %s\n' % baseimage,
                                 img_def.get('build', '')]
        self.buildname = buildname
        self.build_dir = img_def.get('build_directory', None)

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
        print('     * Build directory: %s' % self.build_dir)
        print('     * Intermediate image: %s' % self.buildname)

        dockerfile = '\n'.join(self.dockerfile_lines)

        build_args = dict(tag=self.buildname, pull=pull, nocache=not usecache,
                          decode=True, rm=True)

        if self.build_dir is not None:
            tempdir = self.write_dockerfile(dockerfile)
            build_args.update(fileobj=None,
                              path=os.path.abspath(os.path.expanduser(self.build_dir)),
                              dockerfile=os.path.join(DOCKER_TMPDIR, 'Dockerfile'))
        else:
            build_args.update(fileobj=StringIO(str(dockerfile)),
                              path=None,
                              dockerfile=None)

        # start the build
        stream = client.build(**build_args)

        # monitor the output
        for item in stream:
            if list(item.keys()) == ['stream']:
                print(item['stream'].strip())
            elif 'errorDetail' in item or 'error' in item:
                raise BuildError(dockerfile, item, build_args)
            else:
                print(item, end=' ')

        # remove the temporary dockerfile
        if self.build_dir is not None:
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

    def printfile(self):
        if not os.path.exists('docker_makefiles'):
            os.makedirs('docker_makefiles')
        filename = 'docker_makefiles/Dockerfile.%s' % self.imagename

        with open(filename, 'w') as dfout:
            print('\n'.join(self.dockerfile_lines), file=dfout)


class BuildTarget(object):
    """ Represents a target docker image.

    Args:
        imagename (str): name of the image definition
        targetname (str): name to assign the final built image
        steps (List[BuildStep]): list of steps required to build this image
        stagedfiles (List[StagedFile]): list of files to stage into this image from other images

    """
    def __init__(self, imagename, targetname, steps, stagedfiles):
        self.imagename = imagename
        self.steps = steps
        self.stagedfiles = stagedfiles
        self.targetname = targetname

    def build(self, client,
              printdockerfiles=False, nobuild=False, keepbuildtags=False):
        """
        Drives the build of the final image - get the list of steps and execute them.

        Args:
            client (docker.APIClient): docker client object that will build the image
            printdockerfiles (bool): create the dockerfile for this build
            nobuild (bool): just create dockerfiles, don't actually build the image
            keepbuildtags (bool): keep tags on intermediate images
        """
        print('docker-make starting build for "%s" (image definition "%s"'%(
            self.targetname, self.imagename))
        for istep, step in enumerate(self.steps):
            print('  **** Building %s, Step %d/%d: "%s" requirement ***'%(
                self.imagename,
                istep + 1,
                len(self.steps),
                step.imagename))

            if printdockerfiles:
                step.printfile()

            if not nobuild:
                step.build(client)

        finalimage = step.buildname

        if not nobuild:
            self.finalizenames(client, finalimage, keepbuildtags)

    def finalizenames(self, client, finalimage, keepbuildtags):
        """ Tag the built image with its final name and untag intermediate containers
        """
        client.tag(finalimage, *self.targetname.split(':'))
        print('Tagged final image as %s\n' % self.targetname)
        if not keepbuildtags:
            for step in self.steps:
                client.remove_image(step.buildname, force=True)
                print('Untagged intermediate container "%s"' % step.buildname)


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
