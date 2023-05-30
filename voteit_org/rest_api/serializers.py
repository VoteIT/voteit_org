from rest_framework.serializers import ModelSerializer

from voteit_org.models import ContactInfo


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
