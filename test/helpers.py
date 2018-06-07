import os
import io
import tarfile
import pytest
import docker.errors

__client = None


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
        for name in imgnames:
            try:
                client.images.remove(name, force=True)
            except docker.errors.ImageNotFound:
                pass

        yield

        for name in imgnames:  # force it to also remove the containers
            try:
                client.images.remove(name, force=True)
            except docker.errors.ImageNotFound:
                pass
    return fixture


def assert_file_content(imgname, path, expected_content):
    """ Asserts that an image exists with a file at the
    specified path containing the specified content
    """
    try:
        actual_content = get_file_content(imgname, path)
    except docker.errors.NotFound:
        assert False, ('File %s not found' % path)
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
    content = b''.join(tarstream)
    container.remove()

    tf = tarfile.open(fileobj=io.BytesIO(content))
    val = tf.extractfile(os.path.basename(path)).read().decode('utf-8')
    return val