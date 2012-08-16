import sys
import pylons
pylons.c = pylons.tmpl_context
pylons.g = pylons.app_globals

from djall_rietveld import RietveldApp
from djall_polls import PollsApp
