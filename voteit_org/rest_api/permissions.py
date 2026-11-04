import os
from hmac import compare_digest

from rest_framework.permissions import BasePermission

ORG_LIST_API_KEY = os.getenv("ORG_LIST_API_KEY")


class HasOrgListAPIKey(BasePermission):
    """
    Requires an Api-Key header matching the ORG_LIST_API_KEY env variable.
    """

    def has_permission(self, request, view):
        auth = request.headers.get("Api-Key")
        if not auth:
            return False
        return compare_digest(auth.encode(), ORG_LIST_API_KEY.encode())
