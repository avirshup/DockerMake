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
        image = line[3:]
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
