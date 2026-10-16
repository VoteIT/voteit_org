from rest_framework.serializers import ModelSerializer
from rest_framework.serializers import SerializerMethodField

from voteit.core.rest_api.utils import validate_model_add
from voteit.organisation.models import Organisation

from ..models import ContactInfo


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
        )

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
    url = SerializerMethodField()

    class Meta:
        model = Organisation
        read_only_fields = fields = ("title", "url")

    def get_url(self, obj: Organisation) -> str | None:
        if obj.host:
            return f"https://{obj.host}/"
