import os
import io
import tarfile
import pytest
import docker.errors

__client = None

def _get_client():
    """
    Returns:
        docker.APIClient
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
        client = _get_client()
        for name in imgnames:
            try:
                client.images.remove(name, force=True)
            except docker.errors.ImageNotFound:
                pass

        yield

        for name in imgnames:  # force it to also remove the containers
            client.images.remove(name, force=True)
    return fixture


def assert_file_content(imgname, path, content):
    """ Asserts that an image exists with a file at the
    specified path containing the specified content
    """
    client = _get_client()
    try:
        image = client.images.get(imgname)
    except (docker.errors.ImageNotFound, docker.errors.APIError) as exc:
        assert False, "Image %s not found: %s" % (imgname, exc)

    container = client.containers.create(image)

    try:
        tarstream, stat = container.get_archive(path)
    except docker.errors.NotFound:
        assert False, 'File %s not found' % path
    container.remove()

    tf = tarfile.open(fileobj=io.BytesIO(tarstream.read()))
    val = tf.extractfile(os.path.basename(path)).read().decode('utf-8')
    assert val.strip() == content
