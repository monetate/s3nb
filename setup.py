try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

import s3nb

setup(
    name = 's3nb',
    version = s3nb.__version__,
    author = "Monetate Inc.",
    author_email = "graphaelli@monetate.com",
    description = "s3 backed notebook manager for ipython 2.0+",
    keywords = "ipython",
    license = "Python",
    long_description = """This package enables storage of ipynb files in s3""",
    platforms = 'any',
    py_modules = ['s3nb'],
    url = "https://github.com/monetate/s3nb",
    classifiers = [
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ]
)
