'''
Load the logging config from a file.
'''
from logging.config import fileConfig
from os.path import expanduser


__all__ = ['_']


_ = None  # give importers something to import


fileConfig(f"{expanduser('~')}/logging.config")
