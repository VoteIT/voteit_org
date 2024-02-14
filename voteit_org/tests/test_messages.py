from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test import override_settings
from pydantic import ValidationError

from envelope.messages.errors import BadRequestError
from envelope.messages.errors import UnauthorizedError
from envelope.messages.errors import ValidationErrorMsg

from voteit.meeting.models import Meeting
from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit.poll.app.er_policies.auto_before_poll import AutoBeforePoll
from voteit.poll.app.er_policies.manual import Manual
from voteit.poll.models import ElectoralRegister
from voteit.poll.models import Poll
from voteit_org.messages import ContactInfoGet
from voteit_org.models import ContactInfo

_channel_layers_setting = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}


User = get_user_model()


@override_settings(CHANNEL_LAYERS=_channel_layers_setting)
class GetContactInfoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create()
        cls.manager = cls.org.users.create(username="manager")
        cls.user = cls.org.users.create(username="user")
        cls.org.add_roles(cls.manager, ROLE_ORG_MANAGER)

    @property
    def _cut(self):
        from voteit_org.messages import GetContactInfo

        return GetContactInfo

    def _mk_one(self, user, **kw):
        return self._cut(
            mm={"user_pk": user.pk, "consumer_name": "abc"}, pk=self.org.pk, **kw
        )

    def test_nothing_exist(self):
        msg = self._mk_one(self.manager)
        response = msg.run_job()
        self.assertIsInstance(response, ContactInfoGet)

    def test_with_data(self):
        self.org.contact_info = ContactInfo.objects.create(
            organisation=self.org,
            invoice_info="Important",
            invoice_email="invoice@voteit.se",
        )
        msg = self._mk_one(self.manager)
        response = msg.run_job()
        self.assertIsInstance(response, ContactInfoGet)
        data = response.data.dict(exclude={"modified"})
        self.assertEqual(
            {
                "generic_email": "",
                "invoice_email": "invoice@voteit.se",
                "invoice_info": "Important",
                "organisation": self.org.pk,
                "pk": self.org.contact_info.pk,
                "requires_check": False,
                "text": "",
            },
            data,
        )

    def test_bad_user(self):
        msg = self._mk_one(self.user)
        with self.assertRaises(UnauthorizedError):
            msg.run_job()


@override_settings(CHANNEL_LAYERS=_channel_layers_setting)
class SetContactInfoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = Organisation.objects.create()
        cls.manager = cls.org.users.create(username="manager")
        cls.user = cls.org.users.create(username="user")
        cls.org.add_roles(cls.manager, ROLE_ORG_MANAGER)

    @property
    def _cut(self):
        from voteit_org.messages import SetContactInfo

        return SetContactInfo

    def _mk_one(self, user, **kw):
        return self._cut(mm={"user_pk": user.pk, "consumer_name": "abc"}, **kw)

    def test_nothing_exist(self):
        msg = self._mk_one(
            self.manager, generic_email="hello@betahaus.net", text="Well"
        )
        response = msg.run_job()
        self.assertIsInstance(response, ContactInfoGet)
        self.assertEqual("hello@betahaus.net", self.org.contact_info.generic_email)

    def test_with_data(self):
        self.org.contact_info = ContactInfo.objects.create(
            organisation=self.org,
            invoice_info="Important",
            invoice_email="invoice@voteit.se",
        )
        msg = self._mk_one(
            self.manager, invoice_email="hello@betahaus.net", text="Well"
        )
        response = msg.run_job()
        self.assertIsInstance(response, ContactInfoGet)
        self.org.contact_info.refresh_from_db()
        self.assertEqual("hello@betahaus.net", self.org.contact_info.invoice_email)

    def test_bad_user(self):
        msg = self._mk_one(self.user)
        with self.assertRaises(UnauthorizedError):
            msg.run_job()

    def test_requires_check_updated(self):
        msg = self._mk_one(
            self.manager, generic_email="hello@betahaus.net", text="Well"
        )
        msg.run_job()
        ci = self.org.contact_info
        ci.requires_check = True
        ci.save()
        msg = self._mk_one(
            self.manager, generic_email="hello@betahaus.net", text="Well"
        )
        msg.run_job()
        ci.refresh_from_db()
        self.assertFalse(ci.requires_check)
