from django.apps import AppConfig


class VoteITOrgConfig(AppConfig):
    name = "voteit_org"
    verbose_name = "VoteIT Organisation"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # Register
        from voteit_org import messages  # noqa
        from voteit_org import jobs  # noqa
