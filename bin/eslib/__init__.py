import os
import sys

PY3 = sys.version > '3'
ERIGONES_HOME = os.path.abspath(os.environ.get('ERIGONES_HOME', '/opt/erigones'))
ESLIB = os.path.join(ERIGONES_HOME, 'bin/eslib')
