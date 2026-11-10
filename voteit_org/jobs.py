from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.template import loader
from django.utils.html import strip_tags
from django.utils.timezone import now
from django.core.mail import send_mail

from voteit.core import RQ_LONG_QUEUE
from voteit.core.decorators import job
from voteit.core.decorators import schedule_job
from voteit.core.loggers import notification_logger
from voteit.core.removal import POSTPONE_REMIND
from voteit.core.removal import get_postponed_removals
from voteit.core.removal import postpone_removal
from voteit.organisation.models import Organisation
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit_org.models import ContactInfo


@schedule_job("0 1 * * *")
def org_might_require_check():
    return (
        ContactInfo.objects.filter(requires_check=False, organisation__active=True)
        .filter(
            models.Q(modified__lt=now() - timedelta(days=365))
            | models.Q(invoice_email="")
            | models.Q(generic_email="")
        )
        .update(requires_check=True)
    )


@schedule_job("0 10 15 * *")
def contact_org_about_check():
    """
    Send an email once a month with reminder for those who haven't updated
    """
    contact_qs = (
        ContactInfo.objects.filter(requires_check=True, organisation__active=True)
        .filter(modified__lt=now() - timedelta(days=14))
        .select_related("organisation")
    )
    for contact in contact_qs.exclude(generic_email=""):
        email_org_about_check.enqueue(contact_info_pk=contact.pk)
    if contact_qs.filter(invoice_email="").exists():
        output = "The following active organisations lack generic contact email, so we can't email them about updating their information: \n"
        for contact in contact_qs.filter(invoice_email=""):
            output += f"{contact.organisation.title} @ {contact.organisation.host}\n"
        notification_logger.warning(output)


def render_org_check_email(contact: ContactInfo, org_managers: set[str]) -> str:
    site_url = (
        f"https://{contact.organisation.host}/"  # Good enough, we can assume that :)
    )
    data_protection_contact = None
    if user := contact.data_protection_contact:
        data_protection_contact = user.get_full_name() or user.userid or user.username
    return loader.render_to_string(
        "voteit_org/check_org_email.html",
        context={
            "site_url": site_url,
            "org_title": contact.organisation.title,
            "org_managers": org_managers,
            "data_protection_contact": data_protection_contact,
        },
    )


@job(RQ_LONG_QUEUE)  # Basically for keeping data
def email_org_about_check(contact_info_pk: int):
    contact = ContactInfo.objects.select_related(
        "organisation", "data_protection_contact"
    ).get(pk=contact_info_pk)
    org_managers = {
        x.user.get_full_name()
        for x in contact.organisation.roles.filter(assigned__contains=ROLE_ORG_MANAGER)
        .exclude(user__email__endswith="@betahaus.net")
        .select_related("user")
    }
    html_body = render_org_check_email(contact, org_managers)
    body = strip_tags(html_body)
    send_mail(
        subject="Kolla era uppgifter hos föreningen VoteIT",
        message=body,
        html_message=html_body,
        from_email="support@voteit.se",
        recipient_list=[contact.generic_email],
    )
    output = f"Epostade {contact.organisation.title} @ {contact.organisation.host} på adressen {contact.generic_email} om koll av organisation."
    if not org_managers:
        notification_logger.warning(
            output
            + "\nDet fanns inga aktiva organisationsansvariga, denna organisation behöver hanteras manuellt."
        )
    return output


#: Managers aren't reminded about the same request more often than this.
REMOVAL_REMIND_AGAIN = timedelta(days=3)


@schedule_job("0 12 * * 1-5")  # UTC, so 13 or 14 in Sweden
def remind_about_removal_requests():
    """
    Weekdays: tell each organisation with removal requests that are ready to be
    handled. Repeats until they are, or a manager postpones them.
    """
    user_orgs = dict(
        get_user_model()
        .objects.filter(
            removal_requested__lte=now() - timedelta(hours=settings.REMOVAL_WAIT_HOURS),
            anonymised__isnull=True,
            organisation__active=True,
        )
        .values_list("pk", "organisation_id")
    )
    postponed = get_postponed_removals(user_orgs)
    org_pks = sorted(
        {org_pk for pk, org_pk in user_orgs.items() if pk not in postponed}
    )
    for org_pk in org_pks:
        email_removal_requests.enqueue(organisation_pk=org_pk)
    return len(org_pks)


def get_removal_request_recipients(organisation: Organisation) -> tuple[list, bool]:
    """
    The data protection contact, or the managers when there is none.
    Returns users and whether it's the fallback.
    """
    contact_info = ContactInfo.objects.filter(organisation=organisation).first()
    contact = contact_info and contact_info.data_protection_contact
    if contact and contact.email:
        return [contact], False
    managers = [
        roles.user
        for roles in organisation.roles.filter(assigned__contains=ROLE_ORG_MANAGER)
        .exclude(user__email="")
        .select_related("user")
        .order_by("user_id")
    ]
    return managers, True


@job(RQ_LONG_QUEUE)
def email_removal_requests(organisation_pk: int):
    organisation = Organisation.objects.get(pk=organisation_pk)
    pending_pks = set(
        organisation.users.filter(
            removal_requested__lte=now() - timedelta(hours=settings.REMOVAL_WAIT_HOURS),
            anonymised__isnull=True,
        ).values_list("pk", flat=True)
    )
    pending_pks -= get_postponed_removals(pending_pks).keys()
    pending = len(pending_pks)
    if not pending:
        return
    recipients, fallback = get_removal_request_recipients(organisation)
    if not recipients:
        notification_logger.warning(
            f"{organisation.title} @ {organisation.host} har {pending} begäran(den) "
            "om borttagning, men ingen att maila om dem."
        )
        return
    html_body = loader.render_to_string(
        "voteit_org/removal_requests_email.html",
        context={
            "org_title": organisation.title,
            "site_url": f"https://{organisation.host}/",
            "pending": pending,
            "no_data_protection_contact": fallback,
        },
    )
    send_mail(
        subject="Användare har bett om att bli borttagna",
        message=strip_tags(html_body),
        html_message=html_body,
        from_email="support@voteit.se",
        recipient_list=[user.email for user in recipients],
    )
    # Short of 3 days: this runs just after the daily check, so it must have
    # expired by that check 3 days later.
    until = now() + REMOVAL_REMIND_AGAIN - timedelta(hours=1)
    for user_pk in pending_pks:
        postpone_removal(user_pk, POSTPONE_REMIND, until)
    return f"Mailade {len(recipients)} person(er) på {organisation.title} om {pending} begäran(den) om borttagning."
