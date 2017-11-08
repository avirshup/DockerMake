import os
import pytest
from dockermake.__main__ import _runargs as run_docker_make

from .helpers import assert_file_content, creates_images


# note: these tests MUST be run with CWD REPO_ROOT/tests
@pytest.fixture(scope='session')
def docker_client():
    import docker
    return docker.from_env()


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


def test_dockerfile_write(tmpdir):
    tmpdir = str(tmpdir)
    run_docker_make('-f data/write.yml -p -n --dockerfile-dir %s writetarget' % tmpdir)
    assert os.path.isfile(os.path.join(tmpdir, 'Dockerfile.writetarget'))


img7 = creates_images('simple-target')
@pytest.fixture(scope='function')
def twin_simple_targets(img7, docker_client):
    run_docker_make('-f data/simple.yml simple-target')
    image1 = docker_client.images.get('simple-target')
    run_docker_make('-f data/simple.yml simple-target --no-cache')
    image2 = docker_client.images.get('simple-target')
    return image1, image2


def test_no_cache(twin_simple_targets):
    image1, image2 = twin_simple_targets
    assert image1.id != image2.id

clean8 = creates_images('img1repo/simple-target:img1tag',
                        'img2repo/simple-target:img2tag')
def test_explicit_cache_from(twin_simple_targets, docker_client, clean8):
    image1, image2 = twin_simple_targets
    image1.tag('img1repo/simple-target', tag='img1tag')
    image2.tag('img2repo/simple-target', tag='img2tag')

    run_docker_make('-f data/simple.yml simple-target'
                    ' --cache-repo img1repo --cache-tag img1tag')
    final_image = docker_client.images.get('simple-target')
    assert final_image.id == image1.id


def test_cache_fallback(twin_simple_targets, docker_client):
    image1, image2 = twin_simple_targets

    run_docker_make('-f data/simple.yml simple-target'
                    ' --cache-repo fakerepo --cache-tag faketag')
    final_image = docker_client.images.get('simple-target')
    assert final_image.id == image2.id


def _check_files(img, **present):
    for f, record in _FILES.items():
        if not present.get(f, True):
            with pytest.raises(AssertionError):
                assert_file_content(img, record['path'], record['content'])
        else:
            assert_file_content(img, record['path'], record['content'])


twostep = creates_images('target-twostep',
                         'dmkbuild_target-twostep_2',
                         'dmkbuild_target-twostep_1')
def test_keep_build_tags(twostep, docker_client):
    run_docker_make('-f data/twostep.yml target-twostep --keep-build-tags')
    docker_client.images.get('dmkbuild_target-twostep_1')
    docker_client.images.get('dmkbuild_target-twostep_2')
