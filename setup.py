from setuptools import setup

setup(
    # Application name:
    name="oprex",

    # Version number (initial):
    version="0.1.1",

    # Application author details:
    author="Ron Panduwana",
    author_email="panduwana@gmail.com",

    # Packages
    packages=["app"],

    # Include additional files into the package
    include_package_data=True,

    # Details
    url="http://pypi.python.org/pypi/oprex/",

    #
    # license="LICENSE.txt",
    description="parse some code",

    # long_description=open("README.txt").read(),

    # Dependent packages (distributions)
    install_requires=[
        "argparse>=1.2.1",
		"ply>=3.4",
		"regex>=2014.12.24",
    ],
)