from django.test import TestCase

from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_MEETING_CREATOR
from voteit.organisation.roles import ROLE_ORG_MANAGER

from ..models import ContactInfo


class DeselectDataProtectionContactTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create(host="testserver")
        cls.manager = cls.org.users.create(username="manager")
        cls.org.add_roles(cls.manager, ROLE_ORG_MANAGER, ROLE_MEETING_CREATOR)
        cls.contact_info = ContactInfo.objects.create(
            organisation=cls.org, data_protection_contact=cls.manager
        )

    def _contact(self):
        self.contact_info.refresh_from_db()
        return self.contact_info.data_protection_contact

    def test_manager_role_removed(self):
        self.org.remove_roles(self.manager, ROLE_ORG_MANAGER)
        self.assertIsNone(self._contact())

    def test_other_role_removed(self):
        self.org.remove_roles(self.manager, ROLE_MEETING_CREATOR)
        self.assertEqual(self.manager, self._contact())

    def test_roles_row_deleted(self):
        self.org.roles.filter(user=self.manager).delete()
        self.assertIsNone(self._contact())

    def test_other_managers_change_leaves_it(self):
        other = self.org.users.create(username="other")
        self.org.add_roles(other, ROLE_ORG_MANAGER)
        self.org.remove_roles(other, ROLE_ORG_MANAGER)
        self.assertEqual(self.manager, self._contact())

    def test_user_deleted(self):
        self.manager.delete()
        self.assertIsNone(self._contact())
