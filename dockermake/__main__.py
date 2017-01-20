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
"""
Multiple inheritance for your dockerfiles.
"""
import sys

import yaml

from . import cli
from .imagedefs import ImageDefs


def main():
    args = cli.make_arg_parser().parse_args()

    # Print help and exit
    if args.help_yaml:
        cli.print_yaml_help()
        return

    defs = ImageDefs(args.makefile)

    if args.list:
        list_image_defs(args, defs)
        return

    targets = get_build_targets(args, defs)
    if not targets:
        print 'No build targets specified!'
        list_image_defs(args, defs)
        return

    # Actually build the images! (or just Dockerfiles)
    built, warnings = build_targets(args, defs, targets)

    # Summarize the build process
    print '\ndocker-make finished.'
    print 'Built: '
    for item in built:
        print ' *', item
    if warnings:
        print 'Warnings:'
        for item in warnings:
            print ' *', item


def get_client():
    import docker.utils

    connection = docker.utils.kwargs_from_env()
    if 'tls' in connection:
        connection['tls'].assert_hostname = False
    return docker.Client(**connection)


def list_image_defs(args, defs):
    print 'TARGETS in `%s`' % args.makefile
    for item in defs.ymldefs.keys():
        print ' *', item
    return


def generate_name(image, args):
    repo_base = args.repository if args.repository is not None else ''
    if repo_base[-1] not in ':/':
        repo_base += '/'
    repo_name = repo_base + image
    if args.tag:
        if ':' in repo_name:
            repo_name += '-'+args.tag
        else:
            repo_name += ':'+args.tag

    return repo_name


def get_build_targets(args, defs):
    if args.requires or args.name:
        # Assemble a custom target from requirements
        assert args.requires and args.name
        assert args.name not in defs.ymldefs
        defs.ymldefs[args.name] = {'requires': args.requires}
        targets = [args.name]
    elif args.all:
        # build all targets in the file
        assert len(args.TARGETS) == 0, "Pass either a list of targets or `--all`, not both"
        if defs.all_targets is not None:
            targets = defs.all_targets
        else:
            targets = defs.ymldefs.keys()
    else:
        # build the user-specified targets
        targets = args.TARGETS

    return targets


def build_targets(args, defs, targets):
    if args.no_build:
        client = None
    else:
        client = get_client()
    built, warnings = [], []
    builders = [defs.generate_build(t, generate_name(t, args)) for t in targets]
    for b in builders:
        b.build(client,
                printdockerfiles=args.print_dockerfiles,
                nobuild=args.no_build)
        print '  docker-make built:', b.targetname
        built.append(b.targetname)
        if args.push_to_registry:
            success, w = push(client, b.targetname)
            warnings.extend(w)
            if not success:
                built[-1] += ' -- PUSH FAILED'
            else:
                built[-1] += ' -- pushed to %s' % b.targetname.split('/')[0]

    return built, warnings


def push(client, name):
    success = False
    warnings = []
    if '/' not in name or name.split('/')[0].find('.') < 0:
        warn = 'WARNING: could not push %s - ' \
               'repository name does not contain a registry URL' % name
        warnings.append(warn)
        print warn
    else:
        print '  Pushing %s to %s:' % (name, name.split('/')[0])
        line = {'error': 'no push information received'}
        _lastid = None
        for line in client.push(name, stream=True):
            line = yaml.load(line)
            if 'status' in line:
                if line.get('id', None) == _lastid and line['status'] == 'Pushing':
                    print '\r', line['status'], line['id'], line.get('progress', ''),
                    sys.stdout.flush()
                else:
                    print line['status'], line.get('id', '')
                    _lastid = line.get('id', None)
            else:
                print line
        if 'error' in line:
            warnings.append('WARNING: push failed for %s. Message: %s' % (name, line['error']))
        else:
            success = True
    return success, warnings



__license__ = """Copyright (c) 2016, Autodesk Research
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."""

if __name__ == '__main__':
    main()
