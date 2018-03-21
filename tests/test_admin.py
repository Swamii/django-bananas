from contextlib import contextmanager
from functools import wraps

from django.contrib.auth.models import AnonymousUser, User, Permission
from django.core.management import call_command
from django.test import TestCase

from bananas import admin, compat


@contextmanager
def override_admin_registry():
    initial_registry = admin.site._registry.copy()
    try:
        yield
    finally:
        admin.site._registry = initial_registry


def reset_admin_registry(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        with override_admin_registry():
            return method(*args, **kwargs)

    return wrapped


def get_model_admin_from_registry(admin_view_cls):
    for model, model_admin in admin.site._registry.items():
        if getattr(model, 'View', object) is admin_view_cls:
            return model_admin


class SpecialModelAdmin(admin.ModelAdminView):
    pass


class AdminTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        call_command('syncpermissions')

    def setUp(self):
        super().setUp()
        self.detail_url = compat.reverse('admin:tests_simple')
        self.custom_url = compat.reverse('admin:tests_simple_custom')
        self.special_url = compat.reverse('admin:tests_simple_special')

    def create_user(self, staff=True):
        user = User.objects.create_user(
            username='user', password='test'
        )
        if staff:
            user.is_staff = True
            user.save()
        return user

    def login_user(self, staff=True):
        user = self.create_user(staff=staff)
        self.client.login(username=user.username, password='test')
        return user

    @reset_admin_registry
    def test_admin(self):
        @admin.register
        class AnAdminView(admin.AdminView):
            __module__ = 'tests.admin'

        class FakeRequest:
            META = {'SCRIPT_NAME': ''}
            user = AnonymousUser()

        ctx = admin.site.each_context(FakeRequest())
        self.assertTrue('settings' in ctx)
        self.assertIsInstance(admin.site.urls, tuple)

    @reset_admin_registry
    def test_register_without_args(self):

        # As decorator without arguments
        @admin.register
        class MyAdminViewRegisteredWithoutArgs(admin.AdminView):
            __module__ = 'tests.admin'

        model_admin = get_model_admin_from_registry(
            MyAdminViewRegisteredWithoutArgs
        )
        self.assertIsNotNone(model_admin)
        self.assertIsInstance(model_admin, admin.ModelAdminView)

    @reset_admin_registry
    def test_register_with_args(self):

        # As decorator with arguments
        @admin.register(admin_class=SpecialModelAdmin)
        class MyAdminViewRegisteredWithArgs(admin.AdminView):
            __module__ = 'tests.admin'

        model_admin = get_model_admin_from_registry(
            MyAdminViewRegisteredWithArgs
        )
        self.assertIsNotNone(model_admin)
        self.assertIsInstance(model_admin, SpecialModelAdmin)

    @reset_admin_registry
    def test_register_normally(self):

        # Just registered
        class MyAdminViewRegisteredNormally(admin.AdminView):
            __module__ = 'tests.admin'

        admin.register(
            MyAdminViewRegisteredNormally, admin_class=SpecialModelAdmin
        )
        model_admin = get_model_admin_from_registry(
            MyAdminViewRegisteredNormally
        )
        self.assertIsNotNone(model_admin)
        self.assertIsInstance(model_admin, SpecialModelAdmin)

    def assert_unauthorized(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(
            response,
            '{}?next={}'.format(compat.reverse('admin:login'), url),
            fetch_redirect_response=False,
        )

    def test_admin_view_non_staff(self):
        normal_user = self.login_user(staff=False)
        self.client.login(username=normal_user.username, password='test')

        self.assert_unauthorized(self.custom_url)
        self.assert_unauthorized(self.detail_url)

    def test_admin_view_staff(self):
        staff_user = self.login_user()

        # We need the correct permission
        self.assert_unauthorized(self.custom_url)
        self.assert_unauthorized(self.detail_url)

        perm = Permission.objects.filter(codename='can_access_simple').first()
        self.assertIsNotNone(perm)
        staff_user.user_permissions.add(perm)

        expected_view_tools = {'Even more special action'}

        response = self.client.get(self.custom_url)
        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context['context'], 'custom')
        self.assertEqual(len(context['view_tools']), 1)
        self.assertEqual(
            set(t.text for t in context['view_tools']),
            expected_view_tools
        )

        response = self.client.get(self.detail_url)
        context = response.context
        self.assertEqual(response.status_code, 200)
        self.assertEqual(context['context'], 'get')
        self.assertEqual(len(context['view_tools']), 1)
        self.assertEqual(
            set(t.text for t in context['view_tools']),
            expected_view_tools
        )

    def test_admin_view_with_permission(self):
        staff_user = self.login_user()

        self.assert_unauthorized(self.special_url)

        perm = Permission.objects \
            .filter(codename='can_do_special_stuff') \
            .first()
        self.assertIsNotNone(perm)
        staff_user.user_permissions.add(perm)
        expected_view_tools = {'Special Action', 'Even more special action'}

        response = self.client.get(self.special_url)
        context = response.context
        self.assertEqual(response.status_code, 200)
        self.assertEqual(context['context'], 'special')
        self.assertEqual(len(context['view_tools']), 2)
        self.assertEqual(
            set(t.text for t in context['view_tools']),
            expected_view_tools
        )
        # No access to other views
        self.assert_unauthorized(self.custom_url)
        self.assert_unauthorized(self.detail_url)