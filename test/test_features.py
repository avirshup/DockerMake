import pytest
from dockermake.__main__ import _runargs as run_docker_make

from .helpers import assert_file_content, creates_images


# note: these tests MUST be run with CWD REPO_ROOT/tests

img1 = creates_images(*'target2_bases target3_bases'.split())
def test_multiple_bases(img1):
    run_docker_make('-f data/multibase.yml target2_bases target3_bases')
    assert_file_content('target2_bases', '/opt/success', 'success2')
    assert_file_content('target3_bases', '/opt/success', 'success3')


img2 = creates_images('target_include')
def test_paths_relative_interpreted_relative_to_definition_file(img2):
    run_docker_make('-f data/include.yml target_include')
    assert_file_content('target_include', '/opt/testfile.txt',
                        'this is a file used in tests for relative path resolution')


_FILES = {'a': {'content': 'a', 'path': '/opt/a'},
          'b': {'content': 'b', 'path': '/opt/b'},
          'c': {'content': 'c', 'path': '/opt/c'},
          'd': {'content': 'd', 'path': '/opt/d/d'}}


img3 = creates_images('target_ignore_string')
def test_ignore_string(img3):
    run_docker_make('-f data/ignores.yml target_ignore_string')
    _check_files('target_ignore_string', b=False)


img4 = creates_images('target_ignorefile')
def test_ignorefile(img4):
    run_docker_make('-f data/ignores.yml target_ignorefile')
    _check_files('target_ignorefile', c=False)


img5 = creates_images('target_regular_ignore')
def test_regular_ignore(img5):
    run_docker_make('-f data/ignores.yml target_regular_ignore')
    _check_files('target_regular_ignore', a=False, b=False)


img6 = creates_images('target_ignore_directory')
def test_ignore_directory(img6):
    run_docker_make('-f data/ignores.yml target_ignore_directory')
    _check_files('target_ignore_directory', d=False)


def _check_files(img, **present):
    for f, record in _FILES.items():
        if not present.get(f, True):
            with pytest.raises(AssertionError):
                assert_file_content(img, record['path'], record['content'])
        else:
            assert_file_content(img, record['path'], record['content'])


