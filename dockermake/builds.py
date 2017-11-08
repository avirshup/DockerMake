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
from termcolor import cprint, colored

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
        from_image (str): External base image name
        keepbuildtags (bool): Keep intermediate build tags (dmkbuild_[target]_[stepnum])
    """
    def __init__(self, imagename, targetname, steps, sourcebuilds, from_image, keepbuildtags=False):
        self.imagename = imagename
        self.steps = steps
        self.sourcebuilds = sourcebuilds
        self.targetname = targetname
        self.from_image = from_image
        self.keepbuildtags = keepbuildtags

    def write_dockerfile(self, output_dir):
        """ Used only to write a Dockerfile that will NOT be built by docker-make
        """
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
              usecache=True,
              pull=False):
        """
        Drives the build of the final image - get the list of steps and execute them.

        Args:
            client (docker.Client): docker client object that will build the image
            nobuild (bool): just create dockerfiles, don't actually build the image
            usecache (bool): use docker cache, or rebuild everything from scratch?
            pull (bool): try to pull new versions of repository images?
        """
        if not nobuild:
            self.update_source_images(client,
                                      usecache=usecache,
                                      pull=pull)

        width = utils.get_console_width()
        cprint('\n' + '='*width,
               color='white', attrs=['bold'])

        line = 'STARTING BUILD for "%s" (image definition "%s" from %s)\n' % (
            self.targetname, self.imagename, self.steps[-1].sourcefile)

        cprint(_centered(line, width), color='blue', attrs=['bold'])

        for istep, step in enumerate(self.steps):
            print(colored('* Step','blue'),
                  colored('%d/%d' % (istep+1, len(self.steps)), 'blue', attrs=['bold']),
                  colored('for image', color='blue'),
                  colored(self.imagename, color='blue', attrs=['bold']))

            if not nobuild:
                if step.bust_cache:
                    stackkey = self._get_stack_key(istep)
                    if stackkey in _rebuilt:
                        step.bust_cache = False

                step.build(client, usecache=usecache)
                print(colored("* Created intermediate image", 'green'),
                      colored(step.buildname, 'green', attrs=['bold']),
                      end='\n\n')

                if step.bust_cache:
                    _rebuilt.add(stackkey)

        finalimage = step.buildname

        if not nobuild:
            self.finalizenames(client, finalimage)
            line = 'FINISHED BUILDING "%s" (image definition "%s" from %s)'%(
                self.targetname, self.imagename, self.steps[-1].sourcefile)
            cprint(_centered(line, width),
                   color='green', attrs=['bold'])
            cprint('=' * width, color='white', attrs=['bold'], end='\n\n')

    def _get_stack_key(self, istep):
        names = [self.from_image]
        for i in range(istep+1):
            step = self.steps[i]
            if isinstance(step, FileCopyStep):
                continue
            names.append(step.imagename)
        return tuple(names)

    def update_source_images(self, client, usecache, pull):
        for build in self.sourcebuilds:
            if build.targetname in _updated_staging_images:
                continue
            cprint('\nUpdating source image %s' % build.targetname,
                   'blue')
            build.build(client,
                        usecache=usecache,
                        pull=pull)
            cprint('Finished with build image "%s"\n' % build.targetname,
                   color='green')

    def finalizenames(self, client, finalimage):
        """ Tag the built image with its final name and untag intermediate containers
        """
        client.api.tag(finalimage, *self.targetname.split(':'))
        cprint('Tagged final image as "%s"' % self.targetname,
               'green')
        if not self.keepbuildtags:
            print('Untagging intermediate containers:', end='')
            for step in self.steps:
                client.api.remove_image(step.buildname, force=True)
                print(step.buildname, end=',')
            print()


def _centered(s, w):
    leftover = w - len(s)
    if leftover < 0:
        return s
    else:
        return ' '*(leftover//2) + s