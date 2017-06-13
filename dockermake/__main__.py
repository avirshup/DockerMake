#!/usr/bin/env python
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
"""
Multiple inheritance for your dockerfiles.
"""
from __future__ import print_function
import os
import sys

from . import cli, utils, staging
from .imagedefs import ImageDefs


def main():
    parser = cli.make_arg_parser()
    args = parser.parse_args()

    # print version and exit
    if args.version:
        from . import __version__
        print('docker-make version %s' % __version__)
        return

    # Print help and exit
    if args.help_yaml:
        cli.print_yaml_help()
        return

    if args.clear_copy_cache:
        staging.clear_copy_cache()
        return

    if not os.path.exists(args.makefile):
        print('No docker makefile found at path "%s"'%args.makefile)
        if args.makefile == 'DockerMake.yml':
            print('Type `docker-make --help` to see usage.')
        sys.exit(1)

    defs = ImageDefs(args.makefile)

    if args.list:
        utils.list_image_defs(args, defs)
        return

    targets = utils.get_build_targets(args, defs)
    if not targets:
        print('No build targets specified!')
        utils.list_image_defs(args, defs)
        return

    # Actually build the images! (or just Dockerfiles)
    built, warnings = utils.build_targets(args, defs, targets)

    # Summarize the build process
    print('\ndocker-make finished.')
    print('Built: ')
    for item in built:
        print(' *', item)
    if warnings:
        print('Warnings:')
        for item in warnings:
            print(' *', item)


if __name__ == '__main__':
    main()
