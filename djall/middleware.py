from pylons import c

from allura import model as M

class UserMiddleware(object):

    def process_request(self, request):
        if c.user is M.User.anonymous():
            request.user = None
        else:
            request.user = c.user

