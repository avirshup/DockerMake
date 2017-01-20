from __future__ import print_function
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


def get_client():
    import docker.utils

    connection = docker.utils.kwargs_from_env()
    if 'tls' in connection:
        connection['tls'].assert_hostname = False
    return docker.Client(**connection)


def list_image_defs(args, defs):
    print('TARGETS in `%s`' % args.makefile)
    for item in defs.ymldefs.keys():
        print(' *', item)
    return


def generate_name(image, args):
    repo_base = args.repository

    if repo_base is not None:
        if repo_base[-1] not in ':/':
            repo_base += '/'
        repo_name = repo_base + image
    else:
        repo_name = image

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
        print('  docker-make built:', b.targetname)
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
        print(warn)
    else:
        print('  Pushing %s to %s:' % (name, name.split('/')[0]))
        line = {'error': 'no push information received'}
        _lastid = None
        for line in client.push(name, stream=True):
            line = yaml.load(line)
            if 'status' in line:
                if line.get('id', None) == _lastid and line['status'] == 'Pushing':
                    print('\r', line['status'], line['id'], line.get('progress', ''), end=' ')
                    sys.stdout.flush()
                else:
                    print(line['status'], line.get('id', ''))
                    _lastid = line.get('id', None)
            else:
                print(line)
        if 'error' in line:
            warnings.append('WARNING: push failed for %s. Message: %s' % (name, line['error']))
        else:
            success = True
    return success, warnings
