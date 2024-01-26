from __future__ import annotations

from django.contrib import admin
from voteit.organisation.models import Organisation
from voteit.organisation.admin import OrganisationAdmin as BaseOrganisationAdmin

from voteit_org.models import ContactInfo
from voteit_org.models import Membership
from voteit_org.models import MembershipType


@admin.register(ContactInfo)
class ContactInfoAdmin(admin.ModelAdmin):
    autocomplete_fields = ("organisation",)
    ordering = ("organisation__title",)
    list_display = (
        "organisation",
        "generic_email",
        "requires_check",
        "modified",
    )
    list_filter = (
        "requires_check",
        "organisation__memberships__year",
    )
    search_fields = (
        "organisation__title",
        "text",
    )


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    autocomplete_fields = ("organisation",)
    ordering = ("organisation__title",)
    list_display = (
        "__str__",
        "organisation",
        "year",
        "membership_type",
        "paid",
        # "canceled",
    )
    list_filter = ("year", "paid", "canceled", "membership_type")
    search_fields = (
        "organisation__title",
        "text",
    )


@admin.register(MembershipType)
class MembershipTypeAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "price",
        "active",
    )
    list_filter = ("active",)
    search_fields = (
        "title",
        "description",
    )


class MembershipInline(admin.TabularInline):
    model = Membership
    fields = (
        "year",
        "membership_type",
        "paid",
        "canceled",
    )
    extra = 1


# Replace existing
admin.site.unregister(Organisation)


@admin.register(Organisation)
class OrganisationAdmin(BaseOrganisationAdmin):
    inlines = [MembershipInline]
