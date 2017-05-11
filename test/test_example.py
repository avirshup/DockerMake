import os
import subprocess
import pytest

EXAMPLEDIR = os.path.join('../example')


def test_executable_in_path():
    subprocess.check_call('which docker-make'.split(),
                          cwd=EXAMPLEDIR)


def test_help_string():
    subprocess.check_call('docker-make --help'.split(),
                          cwd=EXAMPLEDIR)


def test_list():
    subprocess.check_call('docker-make --list'.split(),
                          cwd=EXAMPLEDIR)

    output = subprocess.check_output('docker-make --list'.split(),
                                     cwd=EXAMPLEDIR)

    expected = set(('airline_data blank_file_build data_image data_science '
                    'devbase final plant_data python_image').split())

    for line in list(output.splitlines())[4:]:
        image = line[3:].decode('utf-8')
        assert image in expected
        expected.remove(image)

    assert len(expected) == 0


def test_example_build():
    subprocess.check_call(
        "docker-make final --repo myrepo --tag mytag".split(),
        cwd=EXAMPLEDIR)

    subprocess.check_call(
        "docker run myrepo/final:mytag ls data/AirPassengers.csv data/Puromycin.csv data/file.txt".split(),
        cwd=EXAMPLEDIR)


TEMPNAME = 'dmtest__python_test'


def test_write_then_build(tmpdir):
    tmppath = str(tmpdir)
    subprocess.check_call(
            "docker-make -n -p --dockerfile-dir %s python_image" % tmppath,
            shell=True,
            cwd=EXAMPLEDIR)
    subprocess.check_call("docker rm %s; docker build . -f Dockerfile.python_image -t %s" % (TEMPNAME, TEMPNAME),
                          shell=True,
                          cwd=tmppath)
    stdout = subprocess.check_output(
            "docker run %s python -c 'import pint; print 42'" % TEMPNAME,
            shell=True)
    assert int(stdout.strip()) == 42
