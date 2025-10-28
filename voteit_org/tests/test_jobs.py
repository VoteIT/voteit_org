from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from envelope.testing import testing_channel_layers_setting

from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit_org.jobs import email_org_about_check
from voteit_org.jobs import render_org_check_email
from voteit_org.models import ContactInfo


User = get_user_model()


@override_settings(CHANNEL_LAYERS=testing_channel_layers_setting)
class JobsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create(
            title="Den försvunna organisationen", host="test.betahaus.net"
        )
        cls.contact = ContactInfo.objects.create(
            organisation=cls.org, generic_email="hello@betahaus.net"
        )
        cls.manager = cls.org.users.create(
            username="manager", first_name="Someone", last_name="Managerly"
        )
        cls.betahaus_person = cls.org.users.create(
            first_name="Betahaus",
            last_name="Person",
            username="betahaus",
            email="someone@betahaus.net",
        )
        cls.org.add_roles(cls.manager, ROLE_ORG_MANAGER)
        cls.org.add_roles(cls.betahaus_person, ROLE_ORG_MANAGER)

    def test_render_org_check_email(self):
        output = render_org_check_email(self.contact, {"Someone Managerly"})
        self.assertIn("test.betahaus.net", output)
        self.assertIn("Someone Managerly", output)
        self.assertNotIn("Betahaus Person", output)

    def test_email_org_about_check(self):
        email_org_about_check(self.contact.id)
        # Email sent?
        self.assertTrue(mail.outbox)
        msg = mail.outbox[0]
        self.assertEqual(["hello@betahaus.net"], msg.to)
        self.assertEqual("Kolla era uppgifter hos föreningen VoteIT", msg.subject)
        self.assertIn("Kontaktinformation", msg.body)
