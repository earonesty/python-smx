"""Simple python macro expansion"""

from .smx import Smx, __version__
from .wsgi import SmxWsgi

# for command line use of servers
wsgi = SmxWsgi()
