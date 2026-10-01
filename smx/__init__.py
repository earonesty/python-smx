"""Simple python macro expansion"""

__version__ = "0.9.5"

from .smx import Smx
from .wsgi import SmxWsgi

# for command line use of servers
wsgi = SmxWsgi()
