import os.path
from setuptools import setup, find_packages


def read(fname):
    with open(os.path.join(os.path.dirname(__file__), fname)) as fp:
        return fp.read()


long_description = read('README.rst')

install_requires = [
    'coloredlogs>=10.0',
    'Mastodon.py>=1.3.0',
    'mf2py>=1.1.0',
    'mf2util>=0.5.0',
    'python-dateutil>=2.7.0',
    'python-twitter>=3.4.0'
]

tests_require = [
    'pytest>=3.6.2'
]

setup_requires = [
    'setuptools-scm',
    'pytest-runner'
]


setup(
    name='SiloRider',
    use_scm_version={'write_to': 'silorider/version.py'},
    description=("Scans a website's microformats and cross-posts content "
                 "to 'silo' services."),
    long_description=long_description,
    author='Ludovic Chabant',
    author_email='ludovic@chabant.com',
    license="Apache License 2.0",
    url='https://bolt80.com/silorider',
    packages=find_packages(),
    setup_requires=setup_requires,
    tests_require=tests_require,
    install_requires=install_requires,
    entry_points={'console_scripts': [
        'silorider = silorider.main:main'
    ]}
)
