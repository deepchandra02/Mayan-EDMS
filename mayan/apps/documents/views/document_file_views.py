import logging

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.template import RequestContext
from django.urls import reverse
from django.utils.translation import ugettext_lazy as _, ungettext

from mayan.apps.converter.layers import layer_saved_transformations
from mayan.apps.converter.permissions import (
    permission_transformation_delete, permission_transformation_edit
)
from mayan.apps.file_caching.tasks import task_cache_partition_purge
from mayan.apps.sources.links import link_document_file_upload
from mayan.apps.storage.compressed_files import ZipArchive
from mayan.apps.views.generics import (
    ConfirmView, FormView, MultipleObjectDownloadView, SingleObjectEditView,
    MultipleObjectConfirmActionView, MultipleObjectFormActionView,
    SingleObjectDeleteView, SingleObjectDetailView, SingleObjectDownloadView,
    SingleObjectListView
)
from mayan.apps.views.mixins import ExternalObjectMixin

from ..events import event_document_download, event_document_viewed
from ..forms.document_file_forms import (
    DocumentFileDownloadForm, DocumentFileForm, DocumentFilePreviewForm,
    DocumentFilePropertiesForm
)
from ..forms.misc_forms import PageNumberForm
from ..icons import icon_document_file_download, icon_document_file_list
from ..literals import DEFAULT_DOCUMENT_FILE_ZIP_FILENAME
from ..models.document_models import Document
from ..models.document_file_models import DocumentFile
from ..permissions import (
    permission_document_file_delete, permission_document_file_download,
    permission_document_file_edit, permission_document_file_print,
    permission_document_file_tools, permission_document_file_view
)

from .misc_views import PrintFormView, DocumentPrintView

__all__ = (
    'DocumentFileDeleteView', 'DocumentFileDownloadFormView',
    'DocumentFileDownloadView', 'DocumentFileListView',
    'DocumentFilePreviewView'
)
logger = logging.getLogger(name=__name__)


class DocumentFileCachePartitionPurgeView(MultipleObjectConfirmActionView):
    model = DocumentFile
    #object_permission = permission_cache_purge
    pk_url_kwarg = 'document_file_id'
    success_message_singular = '%(count)d document file submitted for cache purging.'
    success_message_plural = '%(count)d document files submitted for cache purging.'

    def get_extra_context(self):
        result = {
            'title': ungettext(
                singular='Submit the selected document file for cache purging?',
                plural='Submit the selected document files for cache purging?',
                number=self.object_list.count()
            )
        }

        if self.object_list.count() == 1:
            result['object'] = self.object_list.first()

        return result

    def object_action(self, form, instance):
        task_cache_partition_purge.apply_async(
            kwargs={
                'cache_partition_id': instance.cache_partition.pk,
                #'user_id': self.request.user.pk
            }
        )
        for page in instance.pages.all():
            task_cache_partition_purge.apply_async(
                kwargs={
                    'cache_partition_id': page.cache_partition.pk,
                    #'user_id': self.request.user.pk
                }
            )


class DocumentFileDeleteView(SingleObjectDeleteView):
    model = DocumentFile
    object_permission = permission_document_file_delete
    pk_url_kwarg = 'document_file_id'

    def get_extra_context(self):
        return {
            'message': _(
                'All document files pages from this document file and the '
                'document version pages linked to them will be deleted too.'
            ),
            'object': self.object,
            'title': _('Delete document file %s ?') % self.object,
        }

    def get_post_action_redirect(self):
        return reverse(
            viewname='documents:document_file_list', kwargs={
                'document_id': self.object.document.pk
            }
        )


'''
class DocumentFileDownloadFormView(MultipleObjectFormActionView):
    form_class = DocumentFileDownloadForm
    model = DocumentFile
    pk_url_kwarg = 'document_file_id'
    querystring_form_fields = (
        'compressed', 'zip_filename', 'preserve_extension'
    )
    viewname = 'documents:document_file_multiple_download'

    def form_valid(self, form):
        # Turn a queryset into a comma separated list of primary keys
        id_list = ','.join(
            [
                force_text(pk) for pk in self.object_list.values_list('pk', flat=True)
            ]
        )

        # Construct URL with querystring to pass on to the next view
        url = furl(
            args={
                'id_list': id_list
            }, path=reverse(viewname=self.viewname)
        )

        # Pass the form field data as URL querystring to the next view
        for field in self.querystring_form_fields:
            data = form.cleaned_data[field]
            if data:
                url.args[field] = data

        return HttpResponseRedirect(redirect_to=url.tostr())

    def get_extra_context(self):

        context = {
            'submit_icon_class': icon_document_file_download,
            'submit_label': _('Download'),
            'subtemplates_list': subtemplates_list,
            'title': _('Download document files')
        }

        if self.object_list.count() == 1:
            context['object'] = self.object_list.first()

        return context

    def get_form_kwargs(self):
        return {
            'queryset': self.object_list
        }
'''

class DocumentFileDownloadView(SingleObjectDownloadView):
    model = DocumentFile
    object_permission = permission_document_file_download
    pk_url_kwarg = 'document_file_id'

    #@staticmethod
    #def commit_event(item, request):
    #    if isinstance(item, Document):
    #        event_document_download.commit(
    #            actor=request.user,
    #            target=item
    #        )
    #    else:
    #        event_document_download.commit(
    #            actor=request.user,
    #            target=item.document
    #        )

    #def get_archive_filename(self):
    #    return self.request.GET.get(
    #        'zip_filename', DEFAULT_DOCUMENT_FILE_ZIP_FILENAME
    #    )

    def get_download_file_object(self):
        #queryset = self.get_object_list()
        #zip_filename = self.get_archive_filename()

        #if self.request.GET.get('compressed') == 'True' or queryset.count() > 1:
        #    compressed_file = ZipArchive()
        #    compressed_file.create()
        #    for item in queryset:
        #        with item.open() as file_object:
        #            compressed_file.add_file(
        #                file_object=file_object,
        #                filename=self.get_item_filename(item=item)
        #            )
        #            DocumentFileDownloadView.commit_event(
        #                item=item, request=self.request
        #            )

        #    compressed_file.close()

        #    return compressed_file.as_file(zip_filename)
        #else:
        #item = queryset.first()
        #DocumentFileDownloadView.commit_event(
        #    item=item, request=self.request
        #)
        event_document_download.commit(
            actor=self.request.user,
            action_object=self.object,
            target=self.object.document
        )

        return self.object.open()

    def get_download_filename(self):
        #queryset = self.get_object_list()
        #if self.request.GET.get('compressed') == 'True' or queryset.count() > 1:
        #    return self.get_archive_filename()
        #else:
        #return self.get_item_filename(item=queryset.first())
        return self.object.get_rendered_string()
    """
    def get_item_filename(self, item):
        preserve_extension = self.request.GET.get(
            'preserve_extension', self.request.POST.get(
                'preserve_extension', False
            )
        )

        preserve_extension = preserve_extension == 'true' or preserve_extension == 'True'

        return item.get_rendered_string(preserve_extension=preserve_extension)
    """


class DocumentFileEditView(SingleObjectEditView):
    form_class = DocumentFileForm
    model = DocumentFile
    object_permission = permission_document_file_edit
    pk_url_kwarg = 'document_file_id'

    def get_extra_context(self):
        return {
            'title': _('Edit document file: %s') % self.object,
        }

    def get_instance_extra_data(self):
        return {
            '_event_actor': self.request.user,
        }

    def get_post_action_redirect(self):
        return reverse(
            viewname='documents:document_file_preview', kwargs={
                'document_file_id': self.object.pk
            }
        )


class DocumentFileListView(ExternalObjectMixin, SingleObjectListView):
    external_object_class = Document
    external_object_permission = permission_document_file_view
    external_object_pk_url_kwarg = 'document_id'

    def get_document(self):
        document = self.external_object
        document.add_as_recent_document_for_user(user=self.request.user)
        return document

    def get_extra_context(self):
        document = self.get_document()
        return {
            'hide_object': True,
            'list_as_items': True,
            'no_results_icon': icon_document_file_list,
            'no_results_main_link': link_document_file_upload.resolve(
                context=RequestContext(
                    dict_={'object': document},
                    request=self.request
                )
            ),
            'no_results_text': _(
                'File are the actual files that were uploaded for each '
                'document. Their contents needs to be mapped to a version '
                'before it can be used.'
            ),
            'no_results_title': _('No files available'),
            'object': document,
            'table_cell_container_classes': 'td-container-thumbnail',
            'title': _('Files of document: %s') % document,
        }

    def get_source_queryset(self):
        return self.get_document().files.order_by('-timestamp')


class DocumentFilePreviewView(SingleObjectDetailView):
    form_class = DocumentFilePreviewForm
    model = DocumentFile
    object_permission = permission_document_file_view
    pk_url_kwarg = 'document_file_id'

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        self.object.document.add_as_recent_document_for_user(
            user=request.user
        )
        event_document_viewed.commit(
            actor=request.user, target=self.object.document
        )

        return result

    def get_extra_context(self):
        return {
            'hide_labels': True,
            'object': self.object,
            'title': _('Preview of document file: %s') % self.object,
        }


class DocumentFilePrintFormView(PrintFormView):
    external_object_class = DocumentFile
    external_object_permission = permission_document_file_print
    external_object_pk_url_kwarg = 'document_file_id'
    print_view_name = 'documents:document_file_print_view'
    print_view_kwarg = 'document_file_id'

    def _add_recent_document(self):
        self.external_object.document.add_as_recent_document_for_user(
            user=self.request.user
        )


class DocumentFilePrintView(DocumentPrintView):
    external_object_class = DocumentFile
    external_object_permission = permission_document_file_print
    external_object_pk_url_kwarg = 'document_file_id'

    def _add_recent_document(self):
        self.external_object.document.add_as_recent_document_for_user(
            user=self.request.user
        )


class DocumentFilePropertiesView(SingleObjectDetailView):
    form_class = DocumentFilePropertiesForm
    model = DocumentFile
    object_permission = permission_document_file_view
    pk_url_kwarg = 'document_file_id'

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        self.object.document.add_as_recent_document_for_user(
            user=request.user
        )
        return result

    def get_extra_context(self):
        return {
            'document_file': self.object,
            'object': self.object,
            'title': _('Properties of document file: %s') % self.object,
        }


class DocumentFileTransformationsClearView(MultipleObjectConfirmActionView):
    model = DocumentFile
    object_permission = permission_transformation_delete
    pk_url_kwarg = 'document_file_id'
    success_message = _(
        'Transformation clear request processed for %(count)d document file.'
    )
    success_message_plural = _(
        'Transformation clear request processed for %(count)d document files.'
    )

    def get_extra_context(self):
        result = {
            'title': ungettext(
                singular='Clear all the page transformations for the selected document file?',
                plural='Clear all the page transformations for the selected document file?',
                number=self.object_list.count()
            )
        }

        if self.object_list.count() == 1:
            result.update(
                {
                    'object': self.object_list.first(),
                    'title': _(
                        'Clear all the page transformations for the '
                        'document file: %s?'
                    ) % self.object_list.first()
                }
            )

        return result

    def object_action(self, form, instance):
        try:
            for page in instance.pages.all():
                layer_saved_transformations.get_transformations_for(
                    obj=page
                ).delete()
        except Exception as exception:
            messages.error(
                message=_(
                    'Error deleting the page transformations for '
                    'document_file: %(document_file)s; %(error)s.'
                ) % {
                    'document_file': instance, 'error': exception
                }, request=self.request
            )


class DocumentFileTransformationsCloneView(ExternalObjectMixin, FormView):
    external_object_class = DocumentFile
    external_object_permission = permission_transformation_edit
    external_object_pk_url_kwarg = 'document_file_id'
    form_class = PageNumberForm

    def dispatch(self, request, *args, **kwargs):
        results = super().dispatch(request=request, *args, **kwargs)
        self.external_object.document.add_as_recent_document_for_user(
            user=request.user
        )

        return results

    def form_valid(self, form):
        try:
            layer_saved_transformations.copy_transformations(
                delete_existing=True, source=form.cleaned_data['page'],
                targets=form.cleaned_data['page'].siblings.exclude(
                    pk=form.cleaned_data['page'].pk
                )
            )
        except Exception as exception:
            if settings.DEBUG:
                raise
            else:
                messages.error(
                    message=_(
                        'Error cloning the page transformations for '
                        'document file: %(document_file)s; %(error)s.'
                    ) % {
                        'document_file': self.external_object,
                        'error': exception
                    }, request=self.request
                )
        else:
            messages.success(
                message=_('Transformations cloned successfully.'),
                request=self.request
            )

        return super().form_valid(form=form)

    def get_form_extra_kwargs(self):
        return {
            'instance': self.external_object
        }

    def get_extra_context(self):
        context = {
            'object': self.external_object,
            'submit_label': _('Submit'),
            'title': _(
                'Clone page transformations of document file: %s'
            ) % self.external_object,
        }

        return context
