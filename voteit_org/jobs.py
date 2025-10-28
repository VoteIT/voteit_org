from datetime import timedelta

from django.db import models
from django.template import loader
from django.utils.html import strip_tags
from django.utils.timezone import now
from django_rq import job
from django.core.mail import send_mail

from voteit.core import RQ_LONG_QUEUE
from voteit.core.loggers import notification_logger
from voteit.organisation.roles import ROLE_ORG_MANAGER
from voteit_org.models import ContactInfo


@job(RQ_LONG_QUEUE)
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


@job(RQ_LONG_QUEUE)
def contact_org_about_check():
    contact_qs = (
        ContactInfo.objects.filter(requires_check=True, organisation__active=True)
        .filter(modified__lt=now() - timedelta(days=14))
        .select_related("organisation")
    )
    for contact in contact_qs.exclude(generic_email=""):
        email_org_about_check.enqueue(contact_info_pk=contact.pk)

    output = "The following active organisations lack generic contact email, so we can't email them about updating their information: \n"
    for contact in contact_qs.filter(invoice_email=""):
        output += f"{contact.organisation.title} @ {contact.organisation.host}\n"
    notification_logger.warning(output)


def render_org_check_email(contact: ContactInfo, org_managers: set[str]) -> str:
    site_url = (
        f"https://{contact.organisation.host}/"  # Good enough, we can assume that :)
    )
    return loader.render_to_string(
        "voteit_org/check_org_email.html",
        context={
            "site_url": site_url,
            "org_title": contact.organisation.title,
            "org_managers": org_managers,
        },
    )


@job(RQ_LONG_QUEUE)  # Basically for keeping data
def email_org_about_check(contact_info_pk: int):
    contact = ContactInfo.objects.get(pk=contact_info_pk)
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
            + "\nDet fanns inga aktiva organisationsansvariga, denna organisation behöver hanteras förmodligen hanteras manuellt."
        )
    return output
