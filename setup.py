from setuptools import setup
from codecs import open

with open("README.rst", "r") as f:
    long_description = f.read()

with open("requirements.txt", "r") as f:
    requirements = f.read().splitlines()


setup(
    name='ready',
    version='0.0.1',
    description='Calculate the redshift of a FRB from its dispersion measure',
    py_modules=["ready"],
    package_dir={"ready": "ready"},
    long_description=long_description,
    install_requires=requirements,

    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
)
