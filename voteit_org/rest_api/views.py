from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from voteit.core import PERM
from voteit.core.rest_api import router
from voteit.core.rest_api.mixins import VerboseAutoPermissionViewSetMixin
from voteit_org.models import ContactInfo
from voteit_org.rest_api.serializers import ContactInfoSerializer
from voteit_org.rest_api.serializers import CreateContactInfoSerializer


@router.register("contact-info", basename="contact-info")
class ContactInfoViewSet(
    VerboseAutoPermissionViewSetMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = ContactInfo.objects.none()
    serializer_class = ContactInfoSerializer
    expected_default_http_status = 404
    permission_type_map = {
        **VerboseAutoPermissionViewSetMixin.permission_type_map,
        "change": "change",
        "create": None,
    }

    def get_object(self):
        try:
            return self.request.user.organisation.contact_info
        except ObjectDoesNotExist:
            raise NotFound()

    def get_serializer_class(self):
        if self.action == "create":
            return CreateContactInfoSerializer
        return super().get_serializer_class()

    def list(self, request, *args, **kwargs):
        """
        A list that may contain one item, but no more.
        """
        instance = self.get_object()
        if not self.request.user.has_perm(ContactInfo.get_perm(PERM.VIEW), instance):
            raise NotFound()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["patch"])
    def change(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        if getattr(instance, "_prefetched_objects_cache", None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}
        return Response(serializer.data)
