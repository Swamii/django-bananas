from bananas.admin import AdminView, register
from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from . import models


@register
class BananasAdmin(AdminView):
    verbose_name = _('Bananas')
    tools = (
        (_('home'), 'admin:index', 'has_access'),
        ('superadmin only', 'https://foo.bar/', 'foobar_permission'),
    )

    def get(self, request):
        return self.render('bananas.html')


@admin.register(models.Monkey)
class MonkeyAdmin(admin.ModelAdmin):
    list_display = ('id',)
    raw_id_fields = ('user',)
    date_hierarchy = 'date_created'
    actions_on_top = True
    actions_on_bottom = True
    actions_selection_counter = False
