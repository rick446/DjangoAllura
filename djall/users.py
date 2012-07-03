from pylons import c
from allura import model as M

class User(object):

    def __init__(self, user):
        self._user = user

    def __getattr__(self, name):
        return getattr(self._user, name)

    def email(self):
        return self._user.username + '@local'
        

def create_login_url(path):
    return '/auth/'

def create_logout_url(path):
    return '/auth/logout'

def get_current_user():
    if c.user is M.User.anonymous():
        return None
    return c.user
