from __future__ import annotations

import csv

from django.contrib import admin
from django.contrib import messages
from django.http import HttpResponse

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
        "is_active",
        "modified",
    )
    list_filter = (
        "organisation__active",
        "requires_check",
        "organisation__memberships__year",
        "modified",
    )
    search_fields = (
        "organisation__title",
        "text",
    )
    actions = ["download_contacts_csv"]

    @admin.display(boolean=True, description="Org active?")
    def is_active(self, instance: ContactInfo):
        return instance.organisation.active

    @admin.action(description="Ladda ner kontakter som CSV")
    def download_contacts_csv(self, request, queryset):
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="kontaktuppgifter_voteit.csv"'
        )
        fieldnames = [
            "organisation__title",
            "generic_email",
            "invoice_email",
            "invoice_info",
            "text",
            "modified",
            "requires_check",
        ]
        writer = csv.DictWriter(response, fieldnames=fieldnames)
        writer.writeheader()  # Custom?
        writer.writerows(x for x in queryset.values(*fieldnames))
        return response


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
    )
    list_filter = (
        "year",
        "paid",
        "membership_type",
        "organisation__active",
    )
    search_fields = (
        "organisation__title",
        "text",
    )
    actions = ["mark_as_paid"]

    @admin.action(description="Mark as paid")
    def mark_as_paid(self, request, queryset):
        queryset = queryset.filter(paid=False)
        changed = queryset.update(paid=True)
        if changed:
            self.message_user(
                request,
                f"Marked {changed} as paid",
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f"Nothing to do, did you select unpaid entries?",
                messages.WARNING,
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
