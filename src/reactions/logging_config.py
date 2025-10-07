'''
Load the logging config from a file.
'''
from logging import DEBUG, addLevelName


__all__ = ['VERBOSE']

# Define a custom log level.
VERBOSE = DEBUG - 5
addLevelName(VERBOSE, 'VERBOSE')

