import subprocess


def test_multiple_bases():
    subprocess.check_call(['docker-make', '-f', 'data/multibase.yml', 'target2', 'target3'])


def test_paths_relative_interpreted_relative_to_definition_file():
    subprocess.check_call(['docker-make', '-f', 'data/include.yml', 'target'])


def test_ignore_string():
    subprocess.check_call(['docker-make', '-f', 'data/ignores.yml', 'target'])

