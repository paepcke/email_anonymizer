import multiprocessing
from setuptools import setup, find_packages

test_requirements = ['sentinels>=0.0.6', 'nose>=1.0']

setup(
    name = "email_anonymizer",
    version = "0.1",
    packages = find_packages(),

    # Dependencies on other packages:
    setup_requires   = ['nose>=1.1.2'],
    tests_require    = test_requirements,
    install_requires = [
                         'mock>=2.0.0',
			] + test_requirements,

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
     #   '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
     #   'hello': ['*.msg'],
    },

    # metadata for upload to PyPI
    author = "Aashna Garg",
    author_email = "paepcke@cs.stanford.edu",
    description = "Anonymizes email traffic for experiments. Mass emailings",
    license = "BSD",
    keywords = "email",
    url = "git@github.com:paepcke/email_anonymizer.git",   # project home page, if any
)
