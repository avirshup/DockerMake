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
from builtins import object

from dockermake.step import FileCopyStep
from . import utils


_updated_staging_images = set()  # stored per session so that we don't try to update them repeatedly
_rebuilt = set()  # only rebuild a unique stack of images ONCE per session


class BuildTarget(object):
    """ Represents a target docker image.

    Args:
        imagename (str): name of the image definition
        targetname (str): name to assign the final built image
        steps (List[BuildStep]): list of steps required to build this image
        stagedfiles (List[StagedFile]): list of files to stage into this image from other images
        from_iamge (str): External base image name
    """
    def __init__(self, imagename, targetname, steps, sourcebuilds, from_image):
        self.imagename = imagename
        self.steps = steps
        self.sourcebuilds = sourcebuilds
        self.targetname = targetname
        self.from_image = from_image

    def write_dockerfile(self, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        lines = []
        for istep, step in enumerate(self.steps):
            if istep == 0:
                lines.extend(step.dockerfile_lines)
            else:
                lines.extend(step.dockerfile_lines[1:])

        path = os.path.join(output_dir, 'Dockerfile.%s' % self.imagename)

        with open(path, 'w') as outfile:
            outfile.write('\n'.join(lines))

        print('Wrote %s' % path)


    def build(self, client,
              nobuild=False,
              keepbuildtags=False,
              usecache=True,
              pull=False):
        """
        Drives the build of the final image - get the list of steps and execute them.

        Args:
            client (docker.APIClient): docker client object that will build the image
            nobuild (bool): just create dockerfiles, don't actually build the image
            keepbuildtags (bool): keep tags on intermediate images
            usecache (bool): use docker cache, or rebuild everything from scratch?
            pull (bool): try to pull new versions of repository images?
        """
        if not nobuild:
            self.update_source_images(client,
                                      usecache=usecache,
                                      pull=pull)

        print('\n' + '-'*utils.get_console_width())
        print('       STARTING BUILD for "%s" (image definition "%s" from %s)\n' % (
            self.targetname, self.imagename, self.steps[-1].sourcefile))

        for istep, step in enumerate(self.steps):
            print(' * Building %s, Step %d/%d:' % (self.imagename,
                                                 istep+1,
                                                 len(self.steps)))

            if not nobuild:
                if step.bust_cache:
                    stackkey = self._get_stack_key(istep)
                    if stackkey in _rebuilt:
                        step.bust_cache = False

                step.build(client, usecache=usecache)
                print("   - Created intermediate image %s\n" % step.buildname)

                if step.bust_cache:
                    _rebuilt.add(stackkey)

        finalimage = step.buildname

        if not nobuild:
            self.finalizenames(client, finalimage, keepbuildtags)
            print(' *** Successfully built image %s\n' % self.targetname)

    def _get_stack_key(self, istep):
        names = [self.from_image]
        for i in xrange(istep+1):
            step = self.steps[i]
            if isinstance(step, FileCopyStep):
                continue
            names.append(step.imagename)
        return tuple(names)

    def update_source_images(self, client, usecache, pull):
        for build in self.sourcebuilds:
            if build.targetname in _updated_staging_images:
                continue
            print('\nUpdating source image %s' % build.targetname)
            build.build(client,
                        usecache=usecache,
                        pull=pull)
            print(' *** Done with source image %s\n' % build.targetname)

    def finalizenames(self, client, finalimage, keepbuildtags):
        """ Tag the built image with its final name and untag intermediate containers
        """
        client.tag(finalimage, *self.targetname.split(':'))
        print('Tagged final image as %s' % self.targetname)
        if not keepbuildtags:
            print('Untagging intermediate containers:', end='')
            for step in self.steps:
                client.remove_image(step.buildname, force=True)
                print(step.buildname, end=',')
            print()
