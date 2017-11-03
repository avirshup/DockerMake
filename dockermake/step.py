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
from io import StringIO, BytesIO
import sys

from termcolor import cprint, colored
import docker.utils, docker.errors

from . import utils
from . import staging
from . import errors
DOCKER_TMPDIR = '_docker_make_tmp/'


class BuildStep(object):
    """ Stores and runs the instructions to build a single image.

    Args:
        imagename (str): name of this image definition
        baseimage (str): base image for this step
        img_def (dict): yaml definition of this image
        buildname (str): what to call this image, once built
        bust_cache(bool): never use docker cache for this build step
    """

    def __init__(self, imagename, baseimage, img_def, buildname,
                 build_first=None, bust_cache=False):
        self.imagename = imagename
        self.baseimage = baseimage
        self.dockerfile_lines = ['FROM %s\n' % baseimage, img_def.get('build', '')]
        self.buildname = buildname
        self.build_dir = img_def.get('build_directory', None)
        self.bust_cache = bust_cache
        self.sourcefile = img_def['_sourcefile']
        self.build_first = build_first
        self.custom_exclude = self._get_ignorefile(img_def)
        self.ignoredefs_file = img_def.get('ignorefile', img_def['_sourcefile'])

    @staticmethod
    def _get_ignorefile(img_def):
        if img_def.get('ignore', None) is not None:
            assert 'ignorefile' not in img_def
            lines = img_def['ignore'].splitlines()
        elif img_def.get('ignorefile', None) is not None:
            assert 'ignore' not in img_def
            with open(img_def['ignorefile'], 'r') as igfile:
                lines = igfile.read().splitlines()
        else:
            return None

        lines.append('_docker_make_tmp')

        return list(filter(bool, lines))

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
        print(colored('  Building step', 'blue'),
              colored(self.imagename, 'blue', attrs=['bold']),
              colored('defined in', 'blue'),
              colored(self.sourcefile, 'blue', attrs=['bold']))

        if self.build_first and not self.build_first.built:
            self.build_external_dockerfile(client, self.build_first)

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
            context_path = os.path.abspath(os.path.expanduser(self.build_dir))
            build_args.update(fileobj=None,
                              dockerfile=os.path.join(DOCKER_TMPDIR, 'Dockerfile'))
            print(colored('  Build context:', 'blue'),
                  colored(os.path.relpath(context_path), 'blue', attrs=['bold']))

            if not self.custom_exclude:
                build_args.update(path=context_path)
            else:
                print(colored('  Custom .dockerignore from:','blue'),
                      colored(os.path.relpath(self.ignoredefs_file),  'blue', attrs=['bold']))
                context = docker.utils.tar(self.build_dir,
                                           exclude=self.custom_exclude,
                                           dockerfile=os.path.join(DOCKER_TMPDIR, 'Dockerfile'),
                                           gzip=False)
                build_args.update(fileobj=context,
                                  custom_context=True)

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
        except (ValueError, docker.errors.APIError) as e:
            raise errors.BuildError(dockerfile, str(e), build_args)

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

    @staticmethod
    def build_external_dockerfile(client, image):
        import docker.errors
        cprint("  Building base image from %s" % image, 'blue')
        assert not image.built

        stream = client.build(path=os.path.dirname(image.path),
                              dockerfile=os.path.basename(image.path),
                              tag=image.tag,
                              decode=True,
                              rm=True)

        try:
            utils.stream_docker_logs(stream, image)
        except (ValueError, docker.errors.APIError) as e:
            raise errors.ExternalBuildError(
                    'Error building Dockerfile at %s.  ' % image.path +
                    'Please check it for errors\n. Docker API error message:' + str(e))
        image.built = True
        cprint("  Finished building Dockerfile at %s" % image.path, 'green')


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
        stage = staging.StagedFile(self.sourceimage, self.sourcepath, self.destpath)
        stage.stage(self.base_image, self.buildname)

    @property
    def dockerfile_lines(self):
        w1 = colored(
                'WARNING: this build includes files that are built in other images!!! The generated'
                '\n         Dockerfile must be built in a directory that contains'
                ' the file/directory:',
                'red', attrs=['bold'])
        w2 = colored('         ' + self.sourcepath, 'red')
        w3 = (colored('         from image ', 'red')
              + colored(self.sourcepath, 'blue', attrs=['bold']))
        print('\n'.join((w1, w2, w3)))
        return ["",
                "# Warning: the file \"%s\" from the image \"%s\""
                " must be present in this build context!!" %
                (self.sourcepath, self.sourceimage),
                "ADD %s %s" % (os.path.basename(self.sourcepath), self.destpath),
                '']

