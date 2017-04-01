from distutils.core import setup
import versioneer

with open('requirements.txt', 'r') as reqfile:
    requirements = [x.strip() for x in reqfile if x.strip()]

setup(
        name='DockerMake',
        version=versioneer.get_version(),
        cmdclass=versioneer.get_cmdclass(),
        packages=['dockermake'],
        license='Apache 2.0',
        author='Aaron Virshup',
        author_email='avirshup@gmail.com',
        description='Build manager for docker images',
        url="https://github.com/avirshup/dockermake",
        entry_points={
                  'console_scripts': [
                      'docker-make = dockermake.__main__:main'
                  ]
        },
        install_requires=requirements,

)
