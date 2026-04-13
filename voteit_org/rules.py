import rules

from voteit.core import PERM
from voteit.organisation.rules import is_manager
from voteit_org.models import ContactInfo


# Electoral register
rules.add_perm(ContactInfo.get_perm(PERM.ADD), is_manager)
rules.add_perm(ContactInfo.get_perm(PERM.CHANGE), is_manager)
rules.add_perm(ContactInfo.get_perm(PERM.VIEW), is_manager)
