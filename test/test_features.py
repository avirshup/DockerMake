import subprocess


def test_multiple_bases():
        subprocess.check_call(['docker-make', '-f', 'data/multibase.yml', 'target2', 'target3'])

