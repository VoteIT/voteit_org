from __future__ import annotations
from datetime import datetime

from django.db import models

from voteit.core.abcs import OrganisationContext
from voteit.core.fields import RichTextField
from voteit.core.utils import relaxed_clean_html
from voteit.organisation.models import Organisation


class ContactInfo(OrganisationContext):
    organisation: Organisation = models.OneToOneField(
        Organisation,
        verbose_name="Organisation",
        on_delete=models.RESTRICT,
        related_name="contact_info",
    )
    text: str = RichTextField(
        verbose_name="Contact text or other notes",
        blank=True,
        default="",
        html_cleaner=relaxed_clean_html,
    )
    generic_email: str = models.EmailField(
        verbose_name="Generic contact email",
        default="",
        blank=True,
    )
    invoice_email: str = models.EmailField(
        verbose_name="Invoice email",
        default="",
        blank=True,
    )
    invoice_info: str = RichTextField(
        verbose_name="Invoice info/address",
        blank=True,
        default="",
        html_cleaner=relaxed_clean_html,
    )
    modified: datetime = models.DateTimeField(
        editable=False,
        auto_now=True,
    )
    requires_check: bool = models.BooleanField(
        verbose_name="Requires check from organisation",
        default=False,
    )

    def __str__(self):
        return f"{self.organisation.title} contacts"

    objects: models.Manager


class Membership(OrganisationContext):
    organisation: Organisation = models.ForeignKey(
        Organisation,
        verbose_name="Organisation",
        on_delete=models.RESTRICT,
        related_name="memberships",
    )
    year: int = models.PositiveSmallIntegerField(
        verbose_name="Year",
    )
    membership_type: MembershipType = models.OneToOneField(
        "MembershipType",
        verbose_name="Membership Type",
        on_delete=models.RESTRICT,
    )
    paid: bool = models.BooleanField(
        verbose_name="Paid?",
        default=False,
    )
    canceled: bool = models.BooleanField(
        verbose_name="Canceled?",
        default=False,
    )
    text: str = models.TextField(
        verbose_name="Comments",
        default="",
        blank=True,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                name="unique_membership_year",
                fields=("organisation", "year"),
            ),
        ]
        get_latest_by = "-year"
        ordering = ["-year"]

    def __str__(self):
        return f"{self.organisation.title} membership {self.year}"

    objects: models.Manager


class MembershipType(models.Model):
    title: str = models.CharField(
        verbose_name="Title",
        max_length=100,
        unique=True,
    )
    description: str = models.TextField(
        verbose_name="Description",
        default="",
        blank=True,
    )
    price: int = models.PositiveIntegerField(
        verbose_name="Price",
    )
    active: bool = models.BooleanField(
        verbose_name="Is this type active?",
        default=True,
    )

    def __str__(self):
        return self.title

    objects: models.Manager
