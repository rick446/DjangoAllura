import os, sys, threading
import pkg_resources

from pylons import c
from ming.utils import LazyProperty

os.environ['DJANGO_SETTINGS_MODULE'] = 'djall_settings_module'

class _DatabaseProxy(dict):

    def __contains__(self, name):
        return name == 'default'

    def __getitem__(self, name):
        return dict(
            ENGINE='django.db.backends.sqlite3',
            OPTIONS={},
            NAME=name,
            USER='',
            PASSWORD='',
            HOST='',
            PORT='')

class _SettingsModule(object):

    def __init__(self):
        self.__file__ = __file__
        self.DATABASES = _DatabaseProxy()
        self.DATABASE_ROUTERS = [ 'djall.db.DatabaseRouter' ]
        self.ROOT_URLCONF = 'djall_urls_module'
        self.DEBUG_PROPAGATE_EXCEPTIONS=True

    @LazyProperty
    def INSTALLED_APPS(self):
        from djall.djall_base import DjangoApp
        result = [
            'django.contrib.auth',
            'django.contrib.contenttypes',
            'django.contrib.sessions',
            'django.contrib.sites',
            # 'django.contrib.messages',
            # 'django.contrib.staticfiles',
            # Uncomment the next line to enable the admin:
                'django.contrib.admin',
            # Uncomment the next line to enable admin documentation:
                # 'django.contrib.admindocs',
            'gae2django',
            'rietveld_helper']
        for ep in pkg_resources.iter_entry_points('allura'):
            value = ep.load()
            if issubclass(value, DjangoApp):
                if value.app_name:
                    result.append(value.app_name)
        return tuple(result)

    @property
    def TEMPLATE_DIRS(self):
        try:
            return c.app.template_dirs
        except TypeError:
            return ()

    @property
    def MEDIA_URL(self):
        try:
            return c.app.media_url
        except TypeError:
            return ''

    @property
    def STATIC_URL(self):
        try:
            return c.app.static_url
        except TypeError:
            return ''

    @property
    def MIDDLEWARE_CLASSES(self):
        return self.__getattr__('MIDDLEWARE_CLASSES')

    def __getattr__(self, name):
        if c.app and name in c.app.extra_settings:
            return c.app.extra_settings[name]
        raise AttributeError, name

class _UrlsProxy(object):

    @property
    def urlpatterns(self):
        return c.app.urlpatterns

import django.conf

class Settings(django.conf.Settings):

    def __init__(self): 

        # store the settings module in case someone later cares
        self.SETTINGS_MODULE = 'djall_settings_module'
        mod = _SettingsModule()

        reserved_names = set(setting for setting in dir(mod) if setting == setting.upper())

        # update this dict from global settings (but only for ALL_CAPS settings
        # not overridden by the settings module)
        for setting in dir(django.conf.global_settings):
            if setting == setting.upper() and setting not in reserved_names:
                try:
                    setattr(self, setting, getattr(django.conf.global_settings, setting))
                except AttributeError, ae:
                    print "can't set attribute: %s (%s)" % (setting, ae)

        self._mod = mod

    def __getattr__(self, name):
        return getattr(self._mod, name)

django.conf.settings = Settings()

sys.modules.update(
    djall_settings_module=_SettingsModule(),
    djall_urls_module=_UrlsProxy())

import django.db.models.loading
from django.utils.datastructures import SortedDict

class AppCache(django.db.models.loading.AppCache):

    def __init__(self):
        self.__state = {}

    @property
    def loaded(self):
        app = c.app
        if app is None: return True
        state = self.__get_state()
        return state['loaded']

    def __getattr__(self, name):
        state = self.__get_state()
        try:
            return state[name]
        except KeyError:
            raise AttributeError, name

    def __setattr__(self, name, value):
        if name.startswith('_') and name != '_get_models_cache':
            return super(AppCache, self).__setattr__(name, value)
        state = self.__get_state()
        state[name] = value

    def __get_state(self):
        app = c.app
        if app is None:
            return {}
        app_id = c.app.config._id
        state = self.__state.setdefault(app_id, {})
        if not state:
            self.__init_state(state)
        return state

    def __init_state(self, d):
        d.update(
            # Keys of app_store are the model modules for each application.
            app_store = SortedDict(),

            # Mapping of installed app_labels to model modules for that app.
            app_labels = {},

            # Mapping of app_labels to a dictionary of model names to model code.
            # May contain apps that are not installed.
            app_models = SortedDict(),

            # Mapping of app_labels to errors raised when trying to import the app.
            app_errors = {},

            # -- Everything below here is only used when populating the cache --
            loaded = False,
            handled = {},
            postponed = [],
            nesting_level = 0,
            write_lock = threading.RLock(),
            _get_models_cache = {},
        )        

if False:
    django.db.models.cache = cache = AppCache()

    # These methods were always module level, so are kept that way for backwards
    # compatibility.
    django.db.models.get_apps = cache.get_apps
    django.db.models.get_app = cache.get_app
    django.db.models.get_app_errors = cache.get_app_errors
    django.db.models.get_models = cache.get_models
    django.db.models.get_model = cache.get_model
    django.db.models.register_models = cache.register_models
    django.db.models.load_app = cache.load_app
    django.db.models.app_cache_ready = cache.app_cache_ready
