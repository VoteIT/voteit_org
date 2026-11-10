from django.db.models.signals import post_delete
from django.db.models.signals import post_save
from django.dispatch import receiver

from voteit.organisation.models import OrganisationRoles
from voteit.organisation.roles import ROLE_ORG_MANAGER

from .models import ContactInfo


@receiver(post_save, sender=OrganisationRoles)
@receiver(post_delete, sender=OrganisationRoles)
def deselect_data_protection_contact(instance: OrganisationRoles, **kwargs):
    """
    Only managers may be the data protection contact. Saves cover Roles.remove()
    and edits of ``assigned``, deletes cover removing the row outright.
    """
    if kwargs.get("raw"):
        return
    if kwargs.get("signal") is post_save and ROLE_ORG_MANAGER in instance.assigned:
        return
    ContactInfo.objects.filter(
        organisation_id=instance.context_id,
        data_protection_contact_id=instance.user_id,
    ).update(data_protection_contact=None)
