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
