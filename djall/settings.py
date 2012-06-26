import os, sys

from pylons import c

os.environ['DJANGO_SETTINGS_MODULE'] = 'djall_settings_module'

class _SettingsModule(object):

    def __init__(self):
        self.DATABASES = _DatabaseProxy()
        self.ROOT_URLCONF = 'djall_urls_module'
        self.MIDDLEWARE_CLASSES = (
            'django.middleware.common.CommonMiddleware',
            # 'django.contrib.sessions.middleware.SessionMiddleware',
            # 'django.middleware.csrf.CsrfViewMiddleware',
            # 'django.contrib.auth.middleware.AuthenticationMiddleware',
            # 'django.contrib.messages.middleware.MessageMiddleware',
            # Uncomment the next line for simple clickjacking protection:
                # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
            )

        self.DEBUG_PROPAGATE_EXCEPTIONS=True
        self.__file__ = __file__

    @property
    def TEMPLATE_DIRS(self):
        return c.app.template_dirs

    @property
    def INSTALLED_APPS(self):
        return c.app.installed_apps

class _DatabaseProxy(dict):

    def __contains__(self, name):
        return name == 'default'

    def __getitem__(self, name):
        if name != 'default': raise KeyError, name
        path = c.app.db_name
        return dict(
            ENGINE='django.db.backends.sqlite3',
            OPTIONS={},
            NAME=path,
            USER='',
            PASSWORD='',
            HOST='',
            PORT='')

class _UrlsProxy(object):

    @property
    def urlpatterns(self):
        return c.app.urlpatterns
        

sys.modules.update(
    djall_settings_module=_SettingsModule(),
    djall_urls_module=_UrlsProxy())
