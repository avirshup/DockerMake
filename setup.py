from distutils.core import setup
import versioneer

setup(
        name='DockerMake',
        version=versioneer.get_version(),
        cmdclass=versioneer.get_cmdclass(),
        packages=['docker-make'],
        license='Apache 2.0',
        author='Aaron Virshup',
        author_email='avirshup@gmail.com',
        description='Build manager for docker images'
)
