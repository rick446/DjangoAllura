import os.path

import tg

from allura.app import Application, DefaultAdminController

from djall import settings

from .controllers import RootController

class DjangoApp(Application):
    app_name = None

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
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        command = syncdb.Command()
        command.execute(verbosity=1, interactive=0, show_traceback=1, database=self.db_name)

    def uninstall(self, project=None, project_id=None):
        'By default, remove the db file'
        os.remove(self.db_name)
