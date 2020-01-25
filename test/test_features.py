import os

import docker.errors
import pytest

from dockermake.__main__ import _runargs as run_docker_make
import dockermake.errors

from . import helpers
from .helpers import experimental_daemon, non_experimental_daemon


# note: these tests MUST be run with CWD REPO_ROOT/tests
@pytest.fixture(scope="session")
def docker_client():
    import docker

    return docker.from_env()


img1 = helpers.creates_images(*"target2_bases target3_bases".split())


def test_multiple_bases(img1):
    run_docker_make("-f data/multibase.yml target2_bases target3_bases")
    helpers.assert_file_content("target2_bases", "/opt/success", "success2")
    helpers.assert_file_content("target3_bases", "/opt/success", "success3")


img2 = helpers.creates_images("target_include")


def test_paths_relative_interpreted_relative_to_definition_file(img2):
    run_docker_make("-f data/include.yml target_include")
    helpers.assert_file_content(
        "target_include",
        "/opt/testfile.txt",
        "this is a file used in tests for relative path resolution",
    )


_FILES = {
    "a": {"content": "a", "path": "/opt/a"},
    "b": {"content": "b", "path": "/opt/b"},
    "c": {"content": "c", "path": "/opt/c"},
    "d": {"content": "d", "path": "/opt/d/d"},
}


def _check_files(img, **present):
    for f, record in _FILES.items():
        if not present.get(f, True):
            with pytest.raises(AssertionError):
                helpers.assert_file_content(img, record["path"], record["content"])
        else:
            helpers.assert_file_content(img, record["path"], record["content"])


img3 = helpers.creates_images("target_ignore_string")


def test_ignore_string(img3):
    run_docker_make("-f data/ignores.yml target_ignore_string")
    _check_files("target_ignore_string", b=False)


img4 = helpers.creates_images("target_ignorefile")


def test_ignorefile(img4):
    run_docker_make("-f data/ignores.yml target_ignorefile")
    _check_files("target_ignorefile", c=False)


img5 = helpers.creates_images("target_regular_ignore")


def test_regular_ignore(img5):
    run_docker_make("-f data/ignores.yml target_regular_ignore")
    _check_files("target_regular_ignore", a=False, b=False)


img6 = helpers.creates_images("target_ignore_directory")


def test_ignore_directory(img6):
    run_docker_make("-f data/ignores.yml target_ignore_directory")
    _check_files("target_ignore_directory", d=False)


def test_dockerfile_write(tmpdir):
    tmpdir = str(tmpdir)
    run_docker_make("-f data/write.yml -p -n --dockerfile-dir %s writetarget" % tmpdir)
    assert os.path.isfile(os.path.join(tmpdir, "Dockerfile.writetarget"))


img7 = helpers.creates_images("simple-target")


@pytest.fixture(scope="function")
def twin_simple_targets(img7, docker_client):
    run_docker_make("-f data/simple.yml simple-target")
    image1 = docker_client.images.get("simple-target")
    run_docker_make("-f data/simple.yml simple-target --no-cache")
    image2 = docker_client.images.get("simple-target")
    return image1, image2


def test_no_cache(twin_simple_targets):
    image1, image2 = twin_simple_targets
    assert image1.id != image2.id


clean8 = helpers.creates_images(
    "img1repo/simple-target:img1tag", "img2repo/simple-target:img2tag"
)


def test_explicit_cache_from(twin_simple_targets, docker_client, clean8):
    image1, image2 = twin_simple_targets
    image1.tag("img1repo/simple-target", tag="img1tag")
    image2.tag("img2repo/simple-target", tag="img2tag")

    run_docker_make(
        "-f data/simple.yml simple-target --cache-repo img1repo --cache-tag img1tag"
    )
    final_image = docker_client.images.get("simple-target")
    assert final_image.id == image1.id


def test_cache_fallback(twin_simple_targets, docker_client):
    image1, image2 = twin_simple_targets

    run_docker_make(
        "-f data/simple.yml simple-target" " --cache-repo fakerepo --cache-tag faketag"
    )
    final_image = docker_client.images.get("simple-target")
    assert final_image.id == image2.id


squashimgs = helpers.creates_images("visible-secret", "invisible-secret")


def test_squashed_secrets(experimental_daemon, squashimgs):
    run_docker_make("-f data/secret-squash.yml invisible-secret visible-secret")
    files_to_find = ["/opt/a", "/root/c", "/root/copy-c"]

    visfiles = helpers.find_files_in_layers("visible-secret", files_to_find)
    assert visfiles["/opt/a"]
    assert not visfiles["/root/c"]
    assert not visfiles["/root/copy-c"]

    invisfiles = helpers.find_files_in_layers("invisible-secret", files_to_find)
    assert invisfiles["/opt/a"]
    assert not invisfiles["/root/c"]
    assert invisfiles["/root/copy-c"]


def test_squashing_error_without_experimental_daemon(non_experimental_daemon):
    with pytest.raises(dockermake.errors.ExperimentalDaemonRequiredError):
        run_docker_make("-f data/secret-squash.yml invisible-secret visible-secret")


squashcache = helpers.creates_images("cache-test")


def test_cache_used_after_squash(experimental_daemon, squashcache):
    run_docker_make("-f data/secret-squash.yml cache-test")
    client = helpers.get_client()
    firstimg = client.images.get("cache-test")
    run_docker_make("-f data/secret-squash.yml cache-test")
    assert client.images.get("cache-test").id == firstimg.id


def test_handle_missing_squash_cache(experimental_daemon, squashcache):
    run_docker_make("-f data/secret-squash.yml cache-test invisible-secret")
    client = helpers.get_client()
    cachelayer = client.images.get("invisible-secret")
    firstimg = client.images.get("cache-test")
    for _id in ("cache-test", firstimg.id, "invisible_secret", cachelayer.id):
        try:
            client.images.remove(_id)
        except docker.errors.ImageNotFound:
            pass

    # Make sure the image can rebuild even if original layers are missing
    run_docker_make("-f data/secret-squash.yml cache-test")

    # Sanity check - makes sure that the first image was in fact removed and not used for cache
    assert client.images.get("cache-test").id != firstimg.id


hassecrets = helpers.creates_images("has-secrets")


def test_secret_files(experimental_daemon, hassecrets):
    run_docker_make("-f data/secret-squash.yml has-secrets")
    foundfiles = helpers.find_files_in_layers(
        "has-secrets",
        ["/root/secret1", "/root/secretdir/secretfile", "/root/copy-of-secret1"],
    )
    assert not foundfiles["/root/secret1"]
    assert not foundfiles["/root/secretdir/secretfile"]
    assert foundfiles["/root/copy-of-secret1"]


secretfail = helpers.creates_images("secretfail")


def test_build_fails_if_secrets_already_exist(experimental_daemon, secretfail):
    with pytest.raises(dockermake.errors.BuildError):
        run_docker_make("-f data/secret-squash.yml secretfail")


copy_with_secrets = helpers.creates_images("copy_with_secrets")


def test_error_if_copy_with_secrets(copy_with_secrets):
    with pytest.raises(dockermake.errors.ParsingFailure):
        run_docker_make("-f data/copy_with_secrets.yml copy_with_secrets")


twostep = helpers.creates_images(
    "target-twostep", "1.target-twostep.dmk", "2.target-twostep.dmk"
)


def test_keep_build_tags(twostep, docker_client):
    run_docker_make("-f data/twostep.yml target-twostep --keep-build-tags")
    assert docker_client.images.list("1.target-twostep.dmk")
    assert docker_client.images.list("2.target-twostep.dmk")


alltest = helpers.creates_images("t1", "t2", "t3", "t4")


def test_implicit_all(alltest):
    run_docker_make("-f data/implicit_all.yml --all")
    for s in "t1 t2 t3 t4".split():
        helpers.assert_file_content(s, "/opt/%s" % s, s)


def test_explicit_all(alltest):
    run_docker_make("-f data/explicit_all.yml --all")
    for s in "t1 t3".split():
        helpers.assert_file_content(s, "/opt/%s" % s, s)
    client = helpers.get_client()
    for s in "t2 t4".split():
        with pytest.raises(docker.errors.ImageNotFound):
            client.images.get(s)


buildargs = helpers.creates_images("target-buildargs")


def test_build_args(buildargs):
    run_docker_make(
        "-f data/build-args.yml --build-arg FILENAME=hello-world.txt target-buildargs"
    )
    helpers.assert_file_content("target-buildargs", "hello-world.txt", "hello world")


abstract_steps = helpers.creates_images("definite", "abstract")


def test_implicit_all_with_abstract_steps(abstract_steps):
    run_docker_make("-f data/abstract-steps.yml --all")
    client = helpers.get_client()
    client.images.get("definite")
    with pytest.raises(docker.errors.ImageNotFound):
        client.images.get("abstract")
