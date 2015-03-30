from __future__ import unicode_literals

from django import apps
from django.utils.translation import ugettext_lazy as _


class MIMETypesApp(apps.AppConfig):
    name = 'mimetype'
    verbose_name = _('MIME types')
