import os.path

import pkg_resources

import tg
from pylons import c

from allura.app import Application, DefaultAdminController, SitemapEntry
from allura.lib.security import has_access
from allura.lib import helpers as h

from .djall_base import DjangoApp
from polls import urls


class PollsApp(DjangoApp):
    __version__ = 0.1
    installable = True
    tool_label ='Polls'
    default_mount_point = 'polls'
    default_mount_label = 'Polls'
    ordinal=200
    icons={
        24:'images/admin_24.png',
        32:'images/admin_32.png',
        48:'images/admin_48.png'
    }

    def __init__(self, project, config):
        super(PollsApp, self).__init__(project, config)
        self.urlpatterns = urls.urlpatterns
        self.template_dirs = [ pkg_resources.resource_filename('polls', 'templates') ]
        self.installed_apps = ( 'polls', )

    def is_visible_to(self, user):
        '''Whether the user can view the app.'''
        return has_access(c.project, 'create')(user=user)

    def main_menu(self):
        '''Apps should provide their entries to be added to the main nav
        :return: a list of :class:`SitemapEntries <allura.app.SitemapEntry>`
        '''
        return [ SitemapEntry(
                self.config.options.mount_label.title(),
                '.')]

    @property
    def sitemap(self):
        menu_id = self.config.options.mount_label.title()
        with h.push_config(c, app=self):
            return [
                SitemapEntry(menu_id, '.')[self.sidebar_menu()] ]

    def sidebar_menu(self):
        return [SitemapEntry('Sidebar', '.')]

    def admin_menu(self):
        return []


        
