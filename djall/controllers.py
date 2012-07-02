from django.core.handlers.wsgi import WSGIHandler

from pylons import c
from tg.controllers import WSGIAppController

class RootController(WSGIAppController):
    _django = WSGIHandler()

    def __init__(self):
        super(RootController, self).__init__(self._django)

    def delegate(self, environ, start_response):
        return super(RootController, self).delegate(environ, start_response)
