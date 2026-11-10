from rest_framework.exceptions import ValidationError
from rest_framework.serializers import ModelSerializer

from voteit.core.rest_api.utils import validate_model_add
from voteit.organisation.models import Organisation

from ..models import ContactInfo
from ..models import is_valid_data_protection_contact


class ContactInfoSerializer(ModelSerializer):
    class Meta:
        model = ContactInfo
        read_only_fields = (
            "pk",
            "organisation",
            "modified",
            "requires_check",
        )
        fields = read_only_fields + (
            "text",
            "generic_email",
            "invoice_email",
            "invoice_info",
            "data_protection_contact",
        )

    def validate_data_protection_contact(self, user):
        if user is not None and not is_valid_data_protection_contact(
            self.context["request"].user.organisation, user
        ):
            raise ValidationError("Must be a manager of this organisation.")
        return user

    def validate(self, attrs):
        attrs = super().validate(attrs)
        attrs["requires_check"] = False
        return attrs


class CreateContactInfoSerializer(ContactInfoSerializer):
    class Meta(ContactInfoSerializer.Meta):
        pass

    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = self.context["request"].user
        attrs["organisation"] = user.organisation
        validate_model_add(self, ContactInfo, user.organisation)
        return attrs


class ActiveOrganisationSerializer(ModelSerializer):
    class Meta:
        model = Organisation
        read_only_fields = fields = ("title", "host")
