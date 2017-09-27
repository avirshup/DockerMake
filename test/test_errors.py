import subprocess
import pytest
from dockermake import errors


ERROR_CODES = {
    'data/circularsource.yml': errors.CircularSourcesError,
    'data/circulardeps.yml': errors.CircularDependencyError,
    'data/multiple.yml': errors.MultipleBaseError,
    'data/conflicting.yml': errors.ConflictingBaseError,
    'data/unrecognized.yml': errors.UnrecognizedKeyError,
    'data/nobase.yml': errors.NoBaseError,
    'data/missingfile.yml': errors.MissingFileError,
    'data/baddockerfile.yml': errors.ExternalBuildError,
    'data/invalid_requires.yml': errors.InvalidRequiresList,
    'data/invalid_yaml.yml': errors.ParsingFailure,
    'data/multi_ignore.yml': errors.MultipleIgnoreError,
}


@pytest.mark.parametrize('item', ERROR_CODES.items(), ids=lambda x:x[0])
def test_errorcodes(item):
    makefile, expected_error = item

    with pytest.raises(subprocess.CalledProcessError):
        try:
            subprocess.check_call(['docker-make', '-f', makefile, 'target'])
        except subprocess.CalledProcessError as exc:
            assert exc.returncode == expected_error.CODE
            raise
