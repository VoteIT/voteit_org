from contextlib import suppress

from django.utils.functional import cached_property
from pydantic import BaseModel
from pydantic import EmailStr
from pydantic import validate_email
from pydantic import validator

from envelope import Error
from envelope.core.message import ContextAction
from envelope.utils import get_error_type
from envelope.utils import websocket_send
from voteit.messaging.base import AddedOrUpdatedSchema
from voteit.messaging.base import BaseObjectAdded
from voteit.messaging.base import BaseObjectChanged
from voteit.messaging.decorators import incoming
from voteit.messaging.decorators import outgoing
from voteit.organisation.models import Organisation
from voteit.organisation.permissions import OrgPermissions
from voteit_org.models import ContactInfo
from voteit_org.rest_api.serializers import ContactInfoSerializer


class ContactInfoSchema(BaseModel):
    """
    >>> ContactInfoSchema().dict()
    {'text': '', 'generic_email': '', 'invoice_email': '', 'invoice_info': ''}
    >>> ContactInfoSchema(generic_email='').dict()
    {'text': '', 'generic_email': '', 'invoice_email': '', 'invoice_info': ''}
    """

    text: str = ""
    generic_email: str = ""
    invoice_email: str = ""
    invoice_info: str = ""

    class Config:
        extra = "allow"
        arbitrary_types_allowed = True

    @validator("generic_email", "invoice_email")
    def optional_email_validation(cls, v: str):
        if v:
            v = v.lower()
            return validate_email(v)[1]
        return ""


@outgoing
class ContactInfoGet(BaseObjectAdded):
    name = "contact_info.get"
    schema = ContactInfoSchema
    data: ContactInfoSchema


class _BaseContactInfo(ContextAction):
    permission = OrgPermissions.MANAGE
    model = Organisation

    @cached_property
    def context(self) -> Organisation:
        return self.user.organisation

    def assert_perm(self):
        if not self.allowed():
            raise get_error_type(Error.UNAUTHORIZED).from_message(
                self,
                model=self.model,
                value=self.context.pk,
                permission=self.permission,
            )


@incoming
class GetContactInfo(_BaseContactInfo):
    name = "contact_info.get"

    def run_job(self) -> ContactInfoGet:
        self.assert_perm()
        data = {}
        with suppress(ContactInfo.DoesNotExist):
            ci = self.context.contact_info
            data = ContactInfoSerializer(ci).data
        response = ContactInfoGet.from_message(self, data=data)
        websocket_send(response, state=response.SUCCESS, on_commit=False)
        return response


@incoming
class SetContactInfo(_BaseContactInfo):
    name = "contact_info.set"
    schema = ContactInfoSchema
    data: ContactInfoSchema

    def run_job(self) -> ContactInfoGet:
        self.assert_perm()
        instance, _ = ContactInfo.objects.update_or_create(
            organisation=self.context,
            defaults=self.data.dict(),
        )
        serializer = ContactInfoSerializer(instance)
        response = ContactInfoGet.from_message(self, data=serializer.data)
        websocket_send(response, state=response.SUCCESS)
        return response
