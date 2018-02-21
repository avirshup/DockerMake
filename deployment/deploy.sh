#!/usr/bin/env sh

# Publish a new release (triggered by a git tag that conforms to a PEP440 release)
# Exit 1 if there's a mismatch between the git tag and the package's version
#
# This runs in the Dockerfile defined in $REPO_ROOT/deployment/Dockerfile

set -e  # fail immediately if any command fails:

PKGNAME=DockerMake
REPO=docker.io/avirshup/DockerMake
distname=${PKGNAME}-${CI_BRANCH}

echo "Now deploying ${distname}"

# Copy python package out of the docker image
docker run dmk-python-3.6 cat dist/${distname}.tar.gz > /opt/dist/${distname}.tar.gz
img=${REPO}:${CI_BRANCH}
docker tag dmk-python-3.6 ${img}


# Push to dockerhub
docker login -u ${DOCKERHUB_USER} -p ${DOCKERHUB_PASSWORD}
docker push ${img} | tee -a push.log | egrep -i 'pull|already'


# Push python package to PyPI
echo "Uploading version ${CI_BRANCH} to PyPI:"
twine upload -u ${PYPI_USER} -p ${PYPI_PASSWORD} /opt/dist/${sdist}
