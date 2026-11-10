from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.test import override_settings
from django.utils.timezone import now

from voteit.core.removal import get_postponed_removals
from voteit.core.removal import postpone_removal
from voteit.core.testing import IsolatedCacheMixin
from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit_org.jobs import email_org_about_check
from voteit_org.jobs import email_removal_requests
from voteit_org.jobs import remind_about_removal_requests
from voteit_org.jobs import render_org_check_email
from voteit_org.models import ContactInfo


User = get_user_model()


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

    def test_render_data_protection_contact(self):
        output = render_org_check_email(self.contact, set())
        self.assertIn("inte valt någon personuppgiftsansvarig", output)
        self.contact.data_protection_contact = self.manager
        output = render_org_check_email(self.contact, set())
        self.assertIn("Personuppgiftsansvarig (PUA)", output)
        self.assertIn("Someone Managerly", output)
        self.assertNotIn("inte valt någon personuppgiftsansvarig", output)

    def test_email_org_about_check(self):
        email_org_about_check(self.contact.id)
        # Email sent?
        self.assertTrue(mail.outbox)
        msg = mail.outbox[0]
        self.assertEqual(["hello@betahaus.net"], msg.to)
        self.assertEqual("Kolla era uppgifter hos föreningen VoteIT", msg.subject)
        self.assertIn("Kontaktinformation", msg.body)
        self.assertIn("inte valt någon personuppgiftsansvarig", msg.body)


@override_settings(REMOVAL_WAIT_HOURS=3)
class RemovalRequestJobsTests(IsolatedCacheMixin, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create(title="Testorg", host="test.voteit.se")
        cls.manager = cls.org.users.create(
            username="manager", email="manager@voteit.se"
        )
        cls.other_manager = cls.org.users.create(
            username="other_manager", email="other@voteit.se"
        )
        cls.staff = cls.org.users.create(username="staff", email="someone@betahaus.net")
        for user in (cls.manager, cls.other_manager, cls.staff):
            cls.org.add_roles(user, ROLE_ORG_MANAGER)
        cls.contact = ContactInfo.objects.create(organisation=cls.org)
        cls.leaving = cls.org.users.create(
            username="leaving", removal_requested=now() - timedelta(hours=4)
        )

    def test_enqueues_per_organisation(self):
        other_org = Organisation.objects.create(host="other")
        other_org.users.create(
            username="other_leaving", removal_requested=now() - timedelta(hours=4)
        )
        # Not ready, anonymised, or inactive organisation
        self.org.users.create(username="early", removal_requested=now())
        self.org.users.create(
            username="done",
            removal_requested=now() - timedelta(days=1),
            anonymised=now(),
        )
        inactive = Organisation.objects.create(host="inactive", active=False)
        inactive.users.create(
            username="ignored", removal_requested=now() - timedelta(days=1)
        )
        with patch.object(email_removal_requests, "enqueue") as enqueue:
            self.assertEqual(2, remind_about_removal_requests())
        self.assertEqual(
            {self.org.pk, other_org.pk},
            {call.kwargs["organisation_pk"] for call in enqueue.call_args_list},
        )

    def test_emails_data_protection_contact(self):
        self.contact.data_protection_contact = self.manager
        self.contact.save()
        email_removal_requests(self.org.pk)
        self.assertEqual(1, len(mail.outbox))
        msg = mail.outbox[0]
        self.assertEqual(["manager@voteit.se"], msg.to)
        self.assertIn("1 användare", msg.body)
        self.assertNotIn("inte har valt någon personuppgiftsansvarig", msg.body)

    def test_emails_managers_without_contact(self):
        email_removal_requests(self.org.pk)
        msg = mail.outbox[0]
        self.assertEqual(
            ["manager@voteit.se", "other@voteit.se", "someone@betahaus.net"], msg.to
        )
        self.assertIn("inte har valt någon personuppgiftsansvarig", msg.body)

    def test_contact_without_email_falls_back(self):
        self.manager.email = ""
        self.manager.save()
        self.contact.data_protection_contact = self.manager
        self.contact.save()
        email_removal_requests(self.org.pk)
        self.assertEqual(["other@voteit.se", "someone@betahaus.net"], mail.outbox[0].to)

    def test_nothing_pending(self):
        self.leaving.anonymised = now()
        self.leaving.save()
        email_removal_requests(self.org.pk)
        self.assertEqual([], mail.outbox)

    def test_nobody_to_email(self):
        self.org.roles.filter(
            user__in=[self.manager, self.other_manager, self.staff]
        ).delete()
        with patch("voteit_org.jobs.notification_logger") as logger:
            email_removal_requests(self.org.pk)
        self.assertEqual([], mail.outbox)
        logger.warning.assert_called_once()

    def test_skips_organisation_with_only_postponed(self):
        postpone_removal(self.leaving.pk, "remind", now() + timedelta(days=1))
        with patch.object(email_removal_requests, "enqueue") as enqueue:
            self.assertEqual(0, remind_about_removal_requests())
        enqueue.assert_not_called()

    def test_postponed_not_emailed_or_counted(self):
        postpone_removal(self.leaving.pk, "block", now() + timedelta(days=1))
        email_removal_requests(self.org.pk)
        self.assertEqual([], mail.outbox)
        self.org.users.create(
            username="also_leaving", removal_requested=now() - timedelta(hours=4)
        )
        email_removal_requests(self.org.pk)
        self.assertIn("1 användare", mail.outbox[0].body)

    def test_emailing_postpones_reminders(self):
        blocked = self.org.users.create(
            username="blocked", removal_requested=now() - timedelta(hours=4)
        )
        block_until = now() + timedelta(days=10)
        postpone_removal(blocked.pk, "block", block_until)
        email_removal_requests(self.org.pk)
        postponed = get_postponed_removals([self.leaving.pk, blocked.pk])
        self.assertEqual("remind", postponed[self.leaving.pk]["kind"])
        self.assertLess(postponed[self.leaving.pk]["until"], now() + timedelta(days=3))
        self.assertGreater(
            postponed[self.leaving.pk]["until"], now() + timedelta(days=2)
        )
        # Not touched
        self.assertEqual({"kind": "block", "until": block_until}, postponed[blocked.pk])
        # So nothing the next day
        mail.outbox.clear()
        email_removal_requests(self.org.pk)
        self.assertEqual([], mail.outbox)

    def test_nobody_to_email_doesnt_postpone(self):
        self.org.roles.filter(
            user__in=[self.manager, self.other_manager, self.staff]
        ).delete()
        email_removal_requests(self.org.pk)
        self.assertEqual({}, get_postponed_removals([self.leaving.pk]))
