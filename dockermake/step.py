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

DOCKER_TMPDIR = "_docker_make_tmp/"


class BuildStep(object):
    """ Stores and runs the instructions to build a single step.

    Args:
        imagename (str): name of this image definition
        baseimage (str): base image for this step
        img_def (dict): yaml definition of this image
        buildname (str): what to call this image, once built
        bust_cache(bool): never use docker cache for this build step
        cache_from (Union[str, List[str]]): use this(these) image(s) to resolve build cache
        buildargs (dict): build-time "buildargs" for dockerfiles
        squash (bool): whether the result should be squashed
        secret_files (List[str]): list of files to delete prior to squashing (squash must be True)
    """

    def __init__(
        self,
        imagename,
        baseimage,
        img_def,
        buildname,
        build_first=None,
        bust_cache=False,
        cache_from=None,
        buildargs=None,
        squash=False,
        secret_files=None,
    ):
        self.imagename = imagename
        self.baseimage = baseimage
        self.img_def = img_def
        self.buildname = buildname
        self.build_dir = img_def.get("build_directory", None)
        self.bust_cache = bust_cache
        self.sourcefile = img_def["_sourcefile"]
        self.build_first = build_first
        self.custom_exclude = self._get_ignorefile(img_def)
        self.ignoredefs_file = img_def.get("ignorefile", img_def["_sourcefile"])
        self.buildargs = buildargs
        self.squash = squash
        self.secret_files = secret_files

        if secret_files:
            assert (
                squash
            ), "Internal error - squash must be set if this step has secret files"

        if cache_from and isinstance(cache_from, str):
            self.cache_from = [cache_from]
        else:
            self.cache_from = cache_from

    @staticmethod
    def _get_ignorefile(img_def):
        if img_def.get("ignore", None) is not None:
            assert "ignorefile" not in img_def
            lines = img_def["ignore"].splitlines()
        elif img_def.get("ignorefile", None) is not None:
            assert "ignore" not in img_def
            with open(img_def["ignorefile"], "r") as igfile:
                lines = igfile.read().splitlines()
        else:
            return None

        lines.append("_docker_make_tmp")

        return list(filter(bool, lines))

    def build(self, client, pull=False, usecache=True):
        """
        Drives an individual build step. Build steps are separated by build_directory.
        If a build has zero one or less build_directories, it will be built in a single
        step.

        Args:
            client (docker.Client): docker client object that will build the image
            pull (bool): whether to pull dependent layers from remote repositories
            usecache (bool): whether to use cached layers or rebuild from scratch
        """
        print(
            colored("  Building step", "blue"),
            colored(self.imagename, "blue", attrs=["bold"]),
            colored("defined in", "blue"),
            colored(self.sourcefile, "blue", attrs=["bold"]),
        )

        if self.build_first and not self.build_first.built:
            self.build_external_dockerfile(client, self.build_first)

        if self.bust_cache:
            usecache = False

        if not usecache:
            cprint(
                "  Build cache disabled - this image will be rebuilt from scratch",
                "yellow",
            )

        dockerfile = "\n".join(self.dockerfile_lines)

        kwargs = dict(
            tag=self.buildname,
            pull=pull,
            nocache=not usecache,
            decode=True,
            rm=True,
            buildargs=self.buildargs,
            squash=self.squash,
        )

        if usecache:
            utils.set_build_cachefrom(self.cache_from, kwargs, client)

        if self.build_dir is not None:
            tempdir = self.write_dockerfile(dockerfile)
            context_path = os.path.abspath(os.path.expanduser(self.build_dir))
            kwargs.update(
                fileobj=None, dockerfile=os.path.join(DOCKER_TMPDIR, "Dockerfile")
            )
            print(
                colored("  Build context:", "blue"),
                colored(os.path.relpath(context_path), "blue", attrs=["bold"]),
            )

            if not self.custom_exclude:
                kwargs.update(path=context_path)
            else:
                print(
                    colored("  Custom .dockerignore from:", "blue"),
                    colored(
                        os.path.relpath(self.ignoredefs_file), "blue", attrs=["bold"]
                    ),
                )

                # AMV - this is a brittle call to an apparently "private' docker sdk method
                context = docker.utils.tar(
                    self.build_dir,
                    exclude=self.custom_exclude,
                    dockerfile=(os.path.join(DOCKER_TMPDIR, "Dockerfile"), dockerfile),
                    gzip=False,
                )
                kwargs.update(fileobj=context, custom_context=True)

        else:
            if sys.version_info.major == 2:
                fileobj = StringIO(dockerfile)
            else:
                fileobj = BytesIO(dockerfile.encode("utf-8"))

            kwargs.update(fileobj=fileobj, path=None, dockerfile=None)

            tempdir = None

        # start the build
        stream = client.api.build(**kwargs)
        try:
            utils.stream_docker_logs(stream, self.buildname)
        except docker.errors.APIError as e:
            if self.squash and not client.version().get("Experimental", False):
                raise errors.ExperimentalDaemonRequiredError(
                    "Docker error message:\n   "
                    + str(e)
                    + "\n\nUsing `squash` and/or `secret_files` requires a docker"
                    " daemon with experimental features enabled. See\n"
                    "    https://github.com/docker/docker-ce/blob/master/components/cli/"
                    "experimental/README.md"
                )
            else:
                raise errors.BuildError(dockerfile, str(e), kwargs)
        except ValueError as e:
            raise errors.BuildError(dockerfile, str(e), kwargs)

        if self.squash and not self.bust_cache:
            self._resolve_squash_cache(client)

        # remove the temporary dockerfile
        if tempdir is not None:
            os.unlink(os.path.join(tempdir, "Dockerfile"))
            os.rmdir(tempdir)

    def _resolve_squash_cache(self, client):
        """
        Currently doing a "squash" basically negates the cache for any subsequent layers.
        But we can work around this by A) checking if the cache was successful for the _unsquashed_
        version of the image, and B) if so, re-using an older squashed version of the image.

        Three ways to do this:
            1. get the shas of the before/after images from `image.history` comments
                OR the output stream (or both). Both are extremely brittle, but also easy to access
           2. Build the image without squash first. If the unsquashed image sha matches
                  a cached one, substitute the unsuqashed image for the squashed one.
                  If no match, re-run the steps with squash=True and store the resulting pair
                  Less brittle than 1., but harder and defs not elegant
           3. Use docker-squash as a dependency - this is by far the most preferable solution,
              except that they don't yet support the newest docker sdk version.

        Currently option 1 is implemented - we parse the comment string in the image history
        to figure out which layers the image was squashed from
        """
        from .staging import BUILD_CACHEDIR

        history = client.api.history(self.buildname)
        comment = history[0].get("Comment", "").split()
        if len(comment) != 4 or comment[0] != "merge" or comment[2] != "to":
            print(
                "WARNING: failed to parse this image's pre-squash history. "
                "The build will continue, but all subsequent layers will be rebuilt."
            )
            return

        squashed_sha = history[0]["Id"]
        start_squash_sha = comment[1]
        end_squash_sha = comment[3]
        cprint(
            "  Layers %s to %s were squashed." % (start_squash_sha, end_squash_sha),
            "yellow",
        )

        # check cache
        squashcache = os.path.join(BUILD_CACHEDIR, "squashes")
        if not os.path.exists(squashcache):
            os.makedirs(squashcache)
        cachepath = os.path.join(
            BUILD_CACHEDIR, "squashes", "%s-%s" % (start_squash_sha, end_squash_sha)
        )

        # on hit, tag the squashedsha as the result of this build step
        if os.path.exists(cachepath):
            self._get_squashed_layer_cache(client, squashed_sha, cachepath)
        else:
            self._cache_squashed_layer(squashed_sha, cachepath)

    def _cache_squashed_layer(self, squashed_sha, cachepath):
        import uuid
        from .staging import BUILD_TEMPDIR

        # store association to the cache. A bit convoluted so that we can use the atomic os.rename

        cprint("  Using newly built layer %s" % squashed_sha, "yellow")
        if not os.path.exists(BUILD_TEMPDIR):
            os.makedirs(BUILD_TEMPDIR)
        writepath = os.path.join(BUILD_TEMPDIR, str(uuid.uuid4()))
        with open(writepath, "w") as shafile:
            shafile.write(squashed_sha)
        os.rename(writepath, cachepath)

    def _get_squashed_layer_cache(self, client, squashed_sha, cachepath):
        with open(cachepath, "r") as cachefile:
            cached_squashed_sha = cachefile.read().strip()

        try:
            client.images.get(cached_squashed_sha)
        except docker.errors.ImageNotFound:
            cprint(
                "  INFO: Old cache image %s no longer exists" % cached_squashed_sha,
                "yellow",
            )
            return self._cache_squashed_layer(squashed_sha, cachepath)
        else:
            cprint(
                "  Using squashed result from cache %s" % cached_squashed_sha, "yellow"
            )
            client.api.tag(cached_squashed_sha, self.buildname, force=True)
            return

    def write_dockerfile(self, dockerfile):
        tempdir = os.path.abspath(os.path.join(self.build_dir, DOCKER_TMPDIR))
        temp_df = os.path.join(tempdir, "Dockerfile")
        if not os.path.isdir(tempdir):
            os.makedirs(tempdir)
        with open(temp_df, "w") as df_out:
            print(dockerfile, file=df_out)
        return tempdir

    @staticmethod
    def build_external_dockerfile(client, image):
        import docker.errors

        cprint("  Building base image from %s" % image, "blue")
        assert not image.built

        stream = client.api.build(
            path=os.path.dirname(image.path),
            dockerfile=os.path.basename(image.path),
            tag=image.tag,
            decode=True,
            rm=True,
        )

        try:
            utils.stream_docker_logs(stream, image)
        except (ValueError, docker.errors.APIError) as e:
            raise errors.ExternalBuildError(
                "Error building Dockerfile at %s.  " % image.path
                + "Please check it for errors\n. Docker API error message:"
                + str(e)
            )
        image.built = True
        cprint("  Finished building Dockerfile at %s" % image.path, "green")

    @property
    def dockerfile_lines(self):
        lines = ["FROM %s\n" % self.baseimage]
        if self.squash:
            lines.append("# This build step should be built with --squash")
        if self.secret_files:
            assert self.squash
            lines.append(
                (
                    "RUN for file in %s; do if [ -e $file ]; then "
                    'echo "ERROR: Secret file $file already exists."; exit 1; '
                    "fi; done;"
                )
                % (" ".join(self.secret_files))
            )
        lines.append(self.img_def.get("build", ""))
        if self.secret_files:
            lines.append("RUN rm -rf %s" % (" ".join(self.secret_files)))
        return lines


class FileCopyStep(BuildStep):
    """
    A specialized build step that copies files into an image from another image.

    Args:
        sourceimage (str): name of image to copy file from
        sourcepath (str): file path in source image
        destpath (str): directory to copy the file into
        imagename (str): name of this image definition
        baseimage (str): base image for this step
        img_def (dict): yaml definition of this image
        buildname (str): what to call this image, once built
        cache_from (str or list): use this(these) image(s) to resolve build cache
    """

    def __init__(self, sourceimage, sourcepath, destpath, *args, **kwargs):
        kwargs.pop("bust_cache", None)
        super(FileCopyStep, self).__init__(*args, **kwargs)
        self.sourceimage = sourceimage
        self.sourcepath = sourcepath
        self.destpath = destpath

    def build(self, client, pull=False, usecache=True):
        """
         Note:
            `pull` and `usecache` are for compatibility only. They're irrelevant because
            hey were applied when BUILDING self.sourceimage
        """
        stage = staging.StagedFile(
            self.sourceimage, self.sourcepath, self.destpath, cache_from=self.cache_from
        )
        stage.stage(self.baseimage, self.buildname)

    @property
    def dockerfile_lines(self):
        """
        Used only when printing dockerfiles, not for building
        """
        w1 = colored(
            "WARNING: this build includes files that are built in other images!!! The generated"
            "\n         Dockerfile must be built in a directory that contains"
            " the file/directory:",
            "red",
            attrs=["bold"],
        )
        w2 = colored("         " + self.sourcepath, "red")
        w3 = colored("         from image ", "red") + colored(
            self.sourcepath, "blue", attrs=["bold"]
        )
        print("\n".join((w1, w2, w3)))
        return [
            "",
            '# Warning: the file "%s" from the image "%s"'
            " must be present in this build context!!"
            % (self.sourcepath, self.sourceimage),
            "ADD %s %s" % (os.path.basename(self.sourcepath), self.destpath),
            "",
        ]
