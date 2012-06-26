import os.path

from . import settings

import pkg_resources

import tg
from pylons import c

from allura.app import Application, DefaultAdminController, SitemapEntry
from allura.lib.security import has_access
from allura.lib import helpers as h

from .controllers import RootController

import django.conf

django.conf.DATABASE_ROUTERS = [ 'djall.db.DatabaseRouter' ]

class DjangoApp(Application):

    def __init__(self, project, config):
        super(DjangoApp, self).__init__(project, config)
        self.admin = DefaultAdminController(self)
        self.root = RootController()

    @property
    def db_name(self):
        location = tg.config['djall_dir']
        return os.path.join(
            '%s/%s-%s.db' % (location, self.project.shortname,
                             self.config.options.mount_point))

    def install(self, project):
        'By default, do a syncdb'
        from django.core.management.commands import syncdb
        command = syncdb.Command()
        command.execute(verbosity=1, interactive=0, show_traceback=1, database='default')

    def uninstall(self, project=None, project_id=None):
        'By default, remove the db file'
        os.remove(self.db_name)
