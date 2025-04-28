from setuptools import setup
import versioneer

setup(
    name="DockerMake",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    packages=["dockermake"],
    license="Apache 2.0",
    author="Aaron Virshup",
    python_requires=">=3.6",
    author_email="avirshup@gmail.com",
    description="Build manager for docker images",
    url="https://github.com/avirshup/dockermake",
    entry_points={"console_scripts": ["docker-make = dockermake.__main__:main"]},
    install_requires=["termcolor", "docker>=4", "pyyaml>=5,<6"],
)
