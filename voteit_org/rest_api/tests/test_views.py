from __future__ import annotations
from typing import TYPE_CHECKING

from django.urls import reverse
from rest_framework.test import APITestCase

from voteit.core.testing import run_permission_tests
from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit_org.models import ContactInfo

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
        self.assertEqual(404, response.status_code)

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
