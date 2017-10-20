from __future__ import print_function

# Copyright 2017 Autodesk Inc.
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
from io import StringIO
import pprint
from termcolor import cprint

class UserException(Exception):
    """
    For errors which should NOT produce a traceback - they should be caught,
    the message written to the CLI, then the program should quit with the specified
    error code
    """
    CODE = None


class MultipleBaseError(UserException):
    CODE = 40


class ConflictingBaseError(UserException):
    CODE = 41


class NoBaseError(UserException):
    CODE = 42


class CircularSourcesError(UserException):
    CODE = 43


class UnrecognizedKeyError(UserException):
    CODE = 44


class CircularDependencyError(UserException):
    CODE = 45


class NoRegistryError(UserException):
    CODE = 46


class MissingFileError(UserException):
    CODE = 47


class ExternalBuildError(UserException):
    CODE = 48


class InvalidRequiresList(UserException):
    CODE = 49


class ParsingFailure(UserException):
    CODE = 50


class MultipleIgnoreError(UserException):
    CODE = 51


class BuildError(Exception):
    CODE = 200

    def __init__(self, dockerfile, item, build_args):
        with open('dockerfile.fail', 'w') as dff:
            print(dockerfile, file=dff)
        with StringIO() as stream:
            cprint('Docker build failure', 'red', attrs=['bold'], file=stream)
            print(u'\n   -------- Docker daemon output --------', file=stream)
            pprint.pprint(item, stream, indent=4)
            print(u'   -------- Arguments to client.build --------', file=stream)
            pprint.pprint(build_args, stream, indent=4)
            print(u'This dockerfile was written to dockerfile.fail', file=stream)
            stream.seek(0)
            super(BuildError, self).__init__(stream.read())
