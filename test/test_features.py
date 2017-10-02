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


img3 = creates_images('target_ignore_string')
def test_ignore_string(img3):
    run_docker_make('-f data/ignores.yml target_ignore_string')
    assert_file_content('target_ignore_string', '/opt/a', 'a')
    with pytest.raises(AssertionError):
        assert_file_content('target_ignore_string', '/opt/b', 'b')
    assert_file_content('target_ignore_string', '/opt/c', 'c')


img4 = creates_images('target_ignorefile')
def test_ignorefile(img4):
    run_docker_make('-f data/ignores.yml target_ignorefile')
    assert_file_content('target_ignorefile', '/opt/a', 'a')
    assert_file_content('target_ignorefile', '/opt/b', 'b')
    with pytest.raises(AssertionError):
        assert_file_content('target_ignorefile', '/opt/c', 'c')


img5 = creates_images('target_regular_ignore')
def test_regular_ignore(img5):
    run_docker_make('-f data/ignores.yml target_regular_ignore')
    with pytest.raises(AssertionError):
        assert_file_content('target_regular_ignore', '/opt/a', 'a')
    with pytest.raises(AssertionError):
        assert_file_content('target_regular_ignore', '/opt/b', 'b')
    assert_file_content('target_regular_ignore', '/opt/c', 'c')
