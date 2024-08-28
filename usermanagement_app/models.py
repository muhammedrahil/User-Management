from django.db import models
import uuid
from django.contrib.auth.models import (
    AbstractBaseUser, BaseUserManager)
from usermanagement_app.utils import get_expire_time
from usermanagement_app.flags import *
from usermanagement_app.validator import validate_profile_image_extension


# Create your models here.

class Platform(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=54, null=True)
    name = models.CharField(max_length=256)
    slug = models.SlugField(blank=True, null=True, unique=False, default=None)
    logo = models.FileField(blank=True, null=True, validators=[validate_profile_image_extension],
                            upload_to='platform/logo/')
    website = models.URLField(max_length=256, null=True)
    domain_url = models.URLField(null=True, blank=True)
    host_url = models.CharField(max_length=256, null=True, blank=True)
    domains_mapped = models.JSONField(null=True, blank=True)
    parent_id = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='platform_parent')
    status = models.PositiveSmallIntegerField(default=PLATFORM_ACTIVE)
    is_super_platform = models.BooleanField(default=False)
    crud_callback_url = models.URLField(default=None, null=True)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Project(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    name = models.CharField(max_length=256)
    logo = models.FileField(blank=True, null=True, upload_to='project/logo/')
    code = models.CharField(max_length=256, null=True)
    website = models.CharField(max_length=256, null=True, blank=True, default=None)
    domain_url = models.URLField(null=True, blank=True)
    host_url = models.CharField(max_length=256, null=True, blank=True)
    domains_mapped = models.JSONField(null=True, blank=True)
    description = models.TextField(null=True)
    parent_id = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, related_name='project_parent')
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='project_platform')
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveIntegerField(blank=False, default=PROJECT_ACTIVE)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class RightName(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    name = models.CharField(max_length=128, blank=False)
    default_right_name = models.BooleanField(default=False)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='rightname_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='rightname_project')
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveIntegerField(blank=False, default=RIGHT_ACTIVE)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class Rights(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    rightname_id = models.ForeignKey(RightName, on_delete=models.CASCADE, null=True, related_name='rights_rightname')
    default_right = models.BooleanField(default=False)
    name = models.CharField(max_length=128, blank=False)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='rights_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='rights_project')
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveIntegerField(blank=False, default=RIGHT_ACTIVE)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at']


class UserType(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    name = models.CharField(max_length=256)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='usertype_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='usertype_project')
    fields = models.JSONField(null=True)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveIntegerField(blank=False, default=USERTYPE_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Roles(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    name = models.CharField(max_length=128, blank=False)
    description = models.TextField(null=True)
    rights_ids = models.ManyToManyField(Rights, blank=True)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='roles_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='roles_project')
    usertype_id = models.ForeignKey(UserType, on_delete=models.SET_NULL, null=True, related_name='roles_usertype')
    created_by = models.CharField(max_length=256, null=True, blank=True)
    updated_by = models.CharField(max_length=256, null=True, blank=True)
    status = models.PositiveIntegerField(blank=False, default=ROLE_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class MemberManager(BaseUserManager):

    def create_user(self, email):
        if email is None:
            raise TypeError('Members must have an email address.')
        member = self.model(email=self.normalize_email(email))
        member.save()
        return member

    def create_superuser(self, username, email, password):
        member = self.create_user(email)
        member.is_superuser = True
        return member


class Member(AbstractBaseUser):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True)
    email_id = models.EmailField(max_length=254, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=88, blank=True, null=True, unique=True)  # validators should be a list
    first_name = models.CharField(max_length=256, null=True, blank=True)
    last_name = models.CharField(max_length=256, null=True, blank=True)
    is_superuser = models.BooleanField(default=False)
    last_login = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True, null=True, default=None)
    status = models.PositiveIntegerField(blank=False, default=1)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email_id'
    REQUIRED_FIELDS = []
    objects = MemberManager()

    class Meta:
        ordering = ['-created_at']


class MemberInformation(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    first_name = models.CharField(max_length=256, null=True, blank=True)
    last_name = models.CharField(max_length=256, null=True, blank=True)
    email_id = models.EmailField(max_length=254, blank=True, null=True)
    phone_number = models.CharField(max_length=88, blank=True, null=True)
    country_code = models.CharField(max_length=10, blank=True, null=True)
    password = models.CharField(blank=True, max_length=256, null=True)
    address_line_1 = models.TextField(null=True)
    address_line_2 = models.TextField(null=True)
    country = models.CharField(max_length=256, null=True)
    state = models.CharField(max_length=256, null=True)
    city = models.CharField(max_length=256, null=True)
    zip_code = models.CharField(max_length=256, null=True, blank=True, default=None)
    profile_image = models.ImageField(blank=True, null=True, validators=[validate_profile_image_extension],
                                      upload_to='member/profile_image/')
    status = models.PositiveIntegerField(default=MEMBER_ACTIVE, choices=MEMBER_PLATFORM_STATUSES)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['first_name', 'last_name']),
            models.Index(fields=['first_name']),
            models.Index(fields=['last_name']),
            models.Index(fields=['email_id']),
            models.Index(fields=['phone_number']),
        ]


class MemberPlatform(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True,
                                    related_name='memberplatform_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='memberplatform_project')
    apple_token = models.TextField(blank=True, null=True)  # this fields add for apple sing in
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, related_name='memberplatform_member')
    memberinformation_id = models.ForeignKey(MemberInformation, on_delete=models.SET_NULL, null=True,
                                             related_name='memberinformation_member')
    roles_id = models.ForeignKey(Roles, on_delete=models.SET_NULL, null=True, related_name='memberplatform_roles')
    usertype_id = models.ForeignKey(UserType, on_delete=models.SET_NULL, null=True,
                                    related_name='memberplatform_usertype')
    device_id = models.TextField(blank=True, null=True, default=None)
    domain_url = models.URLField(null=True, blank=True)
    is_super_admin = models.BooleanField(default=False, null=True, blank=True)
    status = models.PositiveIntegerField(default=MEMBER_PLATFORM_STATUSES[0][0], choices=MEMBER_PLATFORM_STATUSES)
    hide_user = models.BooleanField(default=False, null=True, blank=True)
    is_password_updated = models.BooleanField(default=True, null=True, blank=True)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']


class MemberOtp(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    member_id = models.ForeignKey(Member, on_delete=models.CASCADE, null=True, related_name='memberotp_member')
    otp = models.CharField(max_length=6, default=None)
    is_validated = models.BooleanField(default=False)
    platform_id = models.UUIDField(null=True)
    created_at = models.DateTimeField(auto_now=True)
    expired_at = models.DateTimeField(default=get_expire_time)

    class Meta:
        ordering = ['-created_at']


class MemberLoginActivity(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, related_name="memberloginactivity_member",
                                  null=True)
    logged_in_at = models.DateTimeField(auto_now_add=True)
    device_type = models.CharField(max_length=64, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True)


NOTIFICATION_TYPE = (
    ("forgetpassword_setup", "ForgetPassword_Setup"),
    ("sms_otp", "SMS_OTP"),
    ("mail_otp", "Mail_Otp"),
    ("mail_and_sms", "Mail_And_Sms"),
)


class MailORSMS(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    send_from = models.CharField(max_length=256, null=True)
    send_to = models.CharField(max_length=256, null=True)
    subject = models.CharField(max_length=256, null=True)
    message = models.TextField(null=True)
    type = models.CharField(max_length=256, choices=NOTIFICATION_TYPE, default=NOTIFICATION_TYPE[0][0])
    job_id = models.CharField(max_length=256, null=True)
    status = models.PositiveIntegerField(default=NOTIFICATION_REQUEST_RECEIVED)
    created_at = models.DateTimeField(auto_now_add=True)


class NotificationLog(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True, related_name='notificationlog_member')
    memberplatform_id = models.ForeignKey(MemberPlatform, on_delete=models.SET_NULL, null=True,
                                          related_name='notificationlog_memberplatform')
    mailorsms_id = models.ForeignKey(MailORSMS, on_delete=models.SET_NULL, null=True,
                                     related_name='notificationlog_mailorsms')
    memberotp_id = models.ForeignKey(MemberOtp, on_delete=models.SET_NULL, null=True,
                                     related_name='notificationlog_memberotp')
    status = models.CharField(max_length=256, default=NOTIFICAION_ACTIVE, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class PushNotification(models.Model):
    id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        primary_key=True
    )
    file_name = models.CharField(max_length=256, blank=True, null=True, default=None)
    audio_url = models.TextField(blank=True, null=True, default=None)
    content = models.TextField(blank=True, null=True, default=None)
    member_platform_id = models.ForeignKey(MemberPlatform, on_delete=models.SET_NULL,
                                           related_name="member_push_notification", default=None, null=True)
    message = models.TextField(blank=True, null=True, default=None)
    message_title = models.TextField(blank=True, null=True, default=None)
    message_body = models.TextField(blank=True, null=True, default=None)
    push_notification_response = models.TextField(blank=True, null=True, default=None)
    registration_id = models.CharField(max_length=256, blank=True, null=True, default=None)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class MemberPasswordUniqueIdentifier(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    member_id = models.ForeignKey(Member, on_delete=models.SET_NULL, null=True,
                                  related_name="memberpassworduniqueidentifier_memeber")
    domain_url = models.CharField(max_length=256, null=True, blank=True)
    password_redirect_url = models.CharField(max_length=256, null=True)
    expired = models.PositiveIntegerField(default=VERIFICATION_ACTIVE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class MappedURls(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True,
                                    related_name='mappedurls_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='mappedurls_project')
    domain_url = models.URLField(null=True, blank=True)
    platform_login = models.BooleanField(default=True)
    status = models.PositiveIntegerField(default=ACTIVE)
    created_by = models.CharField(max_length=256, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class FcmKeys(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key = models.TextField(default=None, null=True, blank=True)
    credentials_json = models.FileField(default=None, null=True)
    platform_id = models.ForeignKey(Platform, on_delete=models.SET_NULL, null=True, related_name='fcmkeys_platform')
    project_id = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, related_name='fcmkeys_project')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['platform_id']),
            models.Index(fields=['project_id']),
        ]


class PushNotificationCount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    count = models.PositiveIntegerField(default=0, null=True, blank=True)
    member_platform_id = models.ForeignKey(MemberPlatform, on_delete=models.SET_NULL, null=True, default=None,
                                           related_name="memberplatform_pushnotificationcount")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)


class CallbackLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    response_text = models.TextField(default=None, null=True)
    request_payload = models.JSONField(default=None, null=True)
    response_code = models.PositiveIntegerField(default=None, null=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)


class PushNotificationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message_title = models.TextField(blank=True, null=True, default=None)
    message_body = models.TextField(blank=True, null=True, default=None)
    push_notification_response = models.TextField(blank=True, null=True, default=None)
    registration_ids = models.JSONField(default=None, null=True)
    project_id = models.ForeignKey(Project, default=None, null=True, on_delete=models.SET_NULL,
                                   related_name="pushnotification_log_pr")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
