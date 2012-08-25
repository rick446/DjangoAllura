import os.path

import pkg_resources
import gae2django
gae2django.install()

import tg
from pylons import c
from django.contrib.messages.api import get_messages


from allura.app import Application, DefaultAdminController, SitemapEntry
from allura.lib.security import has_access
from allura.lib import helpers as h
from allura import model as M

from .djall_base import DjangoApp

class RietveldApp(DjangoApp):
    __version__ = 0.1
    installable = True
    tool_label ='Code Review'
    default_mount_point = 'codereview'
    default_mount_label = 'Code Review'
    ordinal=200
    icons={
        24:'images/admin_24.png',
        32:'images/admin_32.png',
        48:'images/admin_48.png'
    }
    app_name = 'codereview'

    def __init__(self, project, config):
        super(RietveldApp, self).__init__(project, config)
        self.template_dirs = [
            pkg_resources.resource_filename('djall', 'templates/rietveld'),
            ]
        self.extra_settings = dict(
            DjangoApp.extra_settings,
            RIETVELD_REVISION = '',
            RIETVELD_INCOMING_MAIL_MAX_SIZE = 500*1024,
            UPLOAD_PY_SOURCE = os.path.join(os.path.dirname(__file__), 'upload.py'),
            DEBUG=False,
            TEMPLATE_DEBUG=False,
            MIDDLEWARE_CLASSES=(
            'django.middleware.common.CommonMiddleware',
            'djall.middleware.UserMiddleware',
            'djall.middleware.DisableCSRFMiddleware',
            'djall.djall_rietveld.AddUserToRequestMiddleware',
            'django.middleware.doc.XViewMiddleware',
            ))
        self.media_url = tg.config['static.script_name'] + config['tool_name'] + '/'
        self.static_url = tg.config['static.script_name'] + config['tool_name'] + '/'
        with h.push_config(c, app=self):
            from codereview import urls
        self.urlpatterns = urls.urlpatterns

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



class AddUserToRequestMiddleware(object):
    """Just add the account..."""

    def process_request(self, request):
        from codereview import models

        account = None
        is_admin = False
        if request.user is not None:
            account = models.Account.get_account_for_user(request.user)
            is_admin = has_access(c.project, 'admin')
        models.Account.current_user_account = account
        request.user_is_admin = is_admin

    def process_view(self, request, view_func, view_args, view_kwargs):
        is_rietveld = view_func.__module__.startswith('codereview')
        user = request.user
        if is_rietveld and user is None:
            # Pre-fetch messages before changing request.user so that
            # they're cached (for Django 1.2.5 and above).
            request._messages = [] # get_messages(request)
            request.user = None
        response = view_func(request, *view_args, **view_kwargs)
        request.user = user
        return response
