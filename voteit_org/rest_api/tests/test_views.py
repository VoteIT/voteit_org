from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

from django.test import override_settings
from django.urls import include
from django.urls import path
from django.urls import reverse
from rest_framework.routers import SimpleRouter
from rest_framework.test import APITestCase

from voteit.core.testing import run_permission_tests
from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER

from ...models import ContactInfo
from ...rest_api.views import ActiveOrganisationsViewSet

if TYPE_CHECKING:
    pass


class ContactInfoViewSetTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org: Organisation = Organisation.objects.create(
            title="Test org", host="testserver"
        )
        cls.manager = cls.org.users.create(username="manager")
        cls.user = cls.org.users.create(username="user")
        cls.org.add_roles(cls.manager, ROLE_ORG_MANAGER)

    def test_create(self):
        url = reverse("contact-info-list")
        data = {
            "title": "Item no 1",
        }
        for func, params in run_permission_tests(
            self,
            url=url,
            data=data,
            method="POST",
            expected=(
                (self.manager, 201, {}),
                (None, 401),
                (self.user, 403),
            ),
        ):
            func(*params)

    def test_list_doest_exist(self):
        url = reverse("contact-info-list")
        self.client.force_authenticate(user=self.manager)
        response = self.client.get(url)
        self.assertEqual(200, response.status_code)
        ci = ContactInfo.objects.get(organisation=self.org)
        self.assertTrue(ci.requires_check)
        self.assertEqual("", ci.invoice_email)
        self.assertEqual("", ci.generic_email)

    def test_list(self):
        ci = ContactInfo.objects.create(
            organisation=self.org,
            invoice_email="bill@somehost.com",
        )
        url = reverse("contact-info-list")
        expected_data = {
            "organisation": self.org.pk,
            "invoice_email": "bill@somehost.com",
            "pk": ci.pk,
        }
        for func, params in run_permission_tests(
            self,
            url=url,
            expected=(
                (self.manager, 200, expected_data),
                (self.user, 404),
                (None, 401),
            ),
        ):
            func(*params)

    def test_patch(self):
        ci = ContactInfo.objects.create(
            organisation=self.org,
            invoice_email="bill@somehost.com",
        )
        url = reverse("contact-info-change")
        data = {"invoice_email": "bill@somehost.com", "text": "Well hello"}
        for func, params in run_permission_tests(
            self,
            url=url,
            data=data,
            method="PATCH",
            expected=(
                (self.manager, 200, {**data, "pk": ci.pk}),
                (self.user, 403),
                (None, 401),
            ),
        ):
            func(*params)


# Registered only when ORG_LIST_API_KEY is set at startup, so the tests route it
# themselves
_router = SimpleRouter()
_router.register(
    "active-organisations",
    ActiveOrganisationsViewSet,
    basename="active-organisations",
)
urlpatterns = [path("api/", include(_router.urls))]


@override_settings(ROOT_URLCONF=__name__)
class ActiveOrganisationsViewSetTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create(title="Active org", host="org.example")
        Organisation.objects.create(title="No host")
        Organisation.objects.create(title="Inactive", host="old.example", active=False)
        cls.url = reverse("active-organisations-list")

    @patch("voteit_org.rest_api.permissions.ORG_LIST_API_KEY", "secret")
    def test_list(self):
        response = self.client.get(self.url, HTTP_API_KEY="secret")
        self.assertEqual(200, response.status_code)
        self.assertEqual(
            [
                {"title": "Active org", "url": "https://org.example/"},
                {"title": "No host", "url": None},
            ],
            response.json(),
        )

    @patch("voteit_org.rest_api.permissions.ORG_LIST_API_KEY", "secret")
    def test_bad_or_missing_key(self):
        self.assertEqual(403, self.client.get(self.url).status_code)
        response = self.client.get(self.url, HTTP_API_KEY="wrong")
        self.assertEqual(403, response.status_code)

    @patch("voteit_org.rest_api.permissions.ORG_LIST_API_KEY", "secret")
    def test_logged_in_user_without_key(self):
        user = self.org.users.create(username="user", is_superuser=True)
        self.client.force_login(user)
        self.assertEqual(403, self.client.get(self.url).status_code)
