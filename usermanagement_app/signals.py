from django.db.models.signals import post_save
from django.dispatch import receiver

from usermanagement_app.models import MemberPlatform, Project
from usermanagement_app.utils import callback_trigger


@receiver(post_save, sender=MemberPlatform, dispatch_uid="member_platform_creation")
def member_platform_creation(sender, instance, **kwargs):
    callback_trigger(instance)


@receiver(post_save, sender=Project, dispatch_uid="project_creation")
def project_creation(sender, instance, **kwargs):
    callback_trigger(instance)