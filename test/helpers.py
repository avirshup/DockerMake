import os
import io
import tarfile
import sys

import pytest
import docker.errors


__client = None
if sys.version_info.major == 2:
    file_not_found_error = IOError
else:
    file_not_found_error = FileNotFoundError


def get_client():
    """
    Returns:
        docker.DockerClient
    """
    global __client
    if __client is None:
        __client = docker.from_env()
    return __client


def creates_images(*imgnames):
    """ Creates fixtures to make sure to remove named images after (and before, if necessary)
    running a test
    """

    @pytest.fixture
    def fixture():
        client = get_client()
        _clean_ctrs_and_imgs(imgnames, client)
        yield
        _clean_ctrs_and_imgs(imgnames, client)

    return fixture


def _clean_ctrs_and_imgs(imgnames, client):
    to_clean = []
    for img in imgnames:
        if ":" in img:
            to_clean.append(img)
        else:
            for img_obj in client.images.list(img):
                to_clean.extend(img_obj.tags)
    for name in to_clean:
        try:
            client.images.remove(name, force=True)
        except docker.errors.ImageNotFound:
            pass


@pytest.fixture
def experimental_daemon():
    _skip_if_daemon_experimental_mode_is(False)


@pytest.fixture
def non_experimental_daemon():
    _skip_if_daemon_experimental_mode_is(True)


def _skip_if_daemon_experimental_mode_is(skip_if_on):
    client = get_client()
    version = client.version()
    if version.get("Experimental", False) == skip_if_on:
        pytest.skip(
            "This test requires a docker daemon with experimental mode *%s*"
            % ("disabled" if skip_if_on else "enabled")
        )


def assert_file_content(imgname, path, expected_content):
    """ Asserts that an image exists with a file at the
    specified path containing the specified content
    """
    try:
        actual_content = get_file_content(imgname, path)
    except docker.errors.NotFound:
        assert False, "File %s not found" % path
    assert actual_content.strip() == expected_content.strip()


def file_exists(imgname, path):
    try:
        get_file_content(imgname, path)
    except docker.errors.NotFound:
        return False
    else:
        return True


def get_file_content(imgname, path):
    client = get_client()
    try:
        image = client.images.get(imgname)
    except (docker.errors.ImageNotFound, docker.errors.APIError) as exc:
        assert False, "Image %s not found: %s" % (imgname, exc)

    container = client.containers.create(image)

    tarstream, stat = container.get_archive(path)
    content = b"".join(tarstream)
    container.remove()

    tf = tarfile.open(fileobj=io.BytesIO(content))
    val = tf.extractfile(os.path.basename(path)).read().decode("utf-8")
    return val


def find_files_in_layers(img, files, tmpdir=None):
    """ Scans an image's layers looking for specific files.

    There's no API for this, so it's brittle. We're looking at
    every layer stored internally for a given image. The solution here just uses `docker save`
    to dump the layers to disk and examine them. This was written to parse the format of the
    tarfile from docker 18.03.1; I'm not sure how stable this is, either backwards or forwards.

    Note that this is used for TESTING ONLY, it's not part of the actual code (right now)

    Args:
        img (str): image id or name
        files (List[str]): list of paths to look for
        tmpdir (str): temporary directory to save

    Returns:
        dict[str, List[str]]: Dict storing the layers each file is present in
    """
    import tempfile
    import json

    client = get_client()
    result = {f: [] for f in files}

    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()

    img = client.images.get(img)
    tarpath = os.path.join(tmpdir, "image.tar")
    with open(tarpath, "wb") as tf:
        for chunk in img.save():
            tf.write(chunk)

    with tarfile.open(tarpath, "r") as tf:
        mf_obj = tf.extractfile("manifest.json")
        manifest = json.loads(mf_obj.read().decode("utf-8"))
        assert len(manifest) == 1
        for path_to_layer_tar in manifest[0]["Layers"]:
            layer_tar_buffer = tf.extractfile(path_to_layer_tar)

            with tarfile.open("r", fileobj=layer_tar_buffer) as layertar:
                layer_results = _scan_tar(layertar, files)
                for f in layer_results:
                    result[f].append(path_to_layer_tar[: -len("layer.tar")])

    return result


def _scan_tar(tarobj, files):
    """ Scans a tar object for specific files.

    Args:
        tarobj (tarfile.TarFile): tar object
        files (List[str]): list of paths to look for

    Returns:
        List[str]: list of the files present (out of the requested paths)
    """
    result = []
    for f in files:
        try:
            tf = tarobj.extractfile(f.lstrip("/"))
        except (KeyError, file_not_found_error):
            continue

        if tf is not None:
            result.append(f)
    return result
