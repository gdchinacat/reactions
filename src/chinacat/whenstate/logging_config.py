'''
Load the logging config from a file.
'''
from logging import DEBUG, addLevelName
from logging.config import fileConfig
from os.path import expanduser


__all__ = ['VERBOSE']

# Define a custom log level.
VERBOSE = DEBUG - 5
addLevelName(VERBOSE, 'VERBOSE')

fileConfig(f"{expanduser('~')}/logging.config")
