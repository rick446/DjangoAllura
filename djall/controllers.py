from django.core.handlers.wsgi import WSGIHandler
from django.shortcuts import render_to_response

from tg.controllers import WSGIAppController

class RootController(WSGIAppController):
    _django = WSGIHandler()

    def __init__(self):
        super(RootController, self).__init__(self._django)

    def delegate(self, environ, start_response):
        result = super(RootController, self).delegate(environ, start_response)
        return result
