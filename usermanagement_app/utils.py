import datetime
import json
import os
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone
import bcrypt
from USER_MANAGEMENT import settings
from usermanagement_app.flags import ACTIVE, PROJECT_ACTIVE, MEMBER_PLATFORM_ACTIVE
import avinit

import boto3
from io import BytesIO
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


def get_expire_time():
    return timezone.now() + timezone.timedelta(minutes=15)


def format_platform_image_url(url):
    return url.replace("//media", "/media")


def get_member_id(request):
    try:
        if request.auth:
            return request.auth['user_id']
    except:
        pass
    return None


def get_platform_id(request):
    try:
        if request.auth:
            return request.auth['platform_id']
    except:
        pass
    return None


def is_super_platform(request):
    try:
        if request.auth:
            return request.auth['is_super_platform']
    except:
        pass
    return False


def get_project_id(request):
    try:
        if request.auth:
            return request.auth['project_id']
    except:
        pass
    return None


def get_memberplatform_id(request):
    try:
        if request.auth:
            return request.auth['memberplatform_id']
    except:
        pass
    return None


def get_request_domain(request):
    """
    Get the domain URL from the request.
    """
    scheme = request.scheme  # Get the scheme (http or https)
    domain = request.META.get('HTTP_HOST')  # Get the host/domain

    # Construct the complete URL
    if scheme and domain:
        url = f'{scheme}://{domain}/'
        if 'http://127.0.0.1:8000/' == url:
            return None
        return url
    else:
        return None  # Return None if the information is not available


def referel_url(request):
    try:
        url = request.headers.get('Referer')
        if url in ['http://127.0.0.1:8000/', 'http://127.0.0.1:5504/', 'http://127.0.0.1:5500/',
                   'http://127.0.0.1:5503/']:
            return None
        return url
    except:
        return None


def hosted_domain_url(request):
    try:
        url = request.headers.get('Referer')
        return url
    except:
        return None


def password_hash(password):
    encode_password = str(password).encode()
    salt = settings.SECRET_KEY.encode()
    hashed_password = bcrypt.hashpw(encode_password, salt)
    hashed_password = hashed_password.decode()
    return hashed_password


def add_slash_in_url(url: str):
    if not url.endswith('/'):
        url += '/'
    return url


def get_children_queryset(filter_queryset, queryset):
    queryset_data = []
    for query in filter_queryset:
        append_dictionary = {
            "id": query.id,
            "title": query.name,
        }
        append_dictionary['subs'] = get_children_queryset(get_child(queryset, query.id), queryset)
        queryset_data.append(append_dictionary)
    return queryset_data


def get_parent(queryset):
    return [single_queryset for single_queryset in queryset if not single_queryset.parent_id_id]


def get_child(queryset, parent_id):
    return [single_queryset for single_queryset in queryset if single_queryset.parent_id_id == parent_id]


def get_children_single_queryset_dropdown(queryset, Model):
    append_list = []
    append_dictionary = {
        "id": queryset.id,
        "title": queryset.name,
    }
    append_dictionary['subs'] = get_child_single_queryset_dropdown(queryset, Model)
    append_list.append(append_dictionary)
    return append_list


def get_child_single_queryset_dropdown(queryset, Model):
    queryset_data = []
    querysets = Model.objects.filter(parent_id=queryset)
    for queryset in querysets:
        append_dictionary = {
            "id": queryset.id,
            "title": queryset.name,
        }
        append_dictionary['subs'] = get_child_single_queryset_dropdown(queryset, Model)
        queryset_data.append(append_dictionary)
    return queryset_data


def get_children_single_queryset(queryset, Model, ModelSerilizer, child=True):
    append_dictionary = ModelSerilizer(queryset).data
    if child:
        append_dictionary['children'] = get_child_single_queryset(queryset, Model, ModelSerilizer)
    return append_dictionary


def get_child_single_queryset(queryset, Model, ModelSerilizer):
    queryset_data = []
    querysets = Model.objects.filter(parent_id=queryset, status=ACTIVE)
    for queryset in querysets:
        append_dictionary = ModelSerilizer(queryset).data
        append_dictionary['children'] = get_child_single_queryset(queryset, Model, ModelSerilizer)
        queryset_data.append(append_dictionary)
    return queryset_data


def hierarchy_names(model):
    hierarchy = []
    reverse_hierarchy(model, hierarchy)
    return hierarchy


def reverse_hierarchy(model, hierarchy: list):
    if model:
        hierarchy.insert(0, {"id": str(model.id), "name": model.name})
        reverse_hierarchy(model.parent_id, hierarchy)
    return hierarchy


def default_rights():
    return ["platform", "project", "role", "right", "usertype", "member"]


# def create_avatar(name: str, which):
#     if not os.path.exists('media'):
#         os.mkdir("media")
#     UPLOAD_FOLDER = f"media/{which}"
#     if not os.path.exists(UPLOAD_FOLDER):
#         os.mkdir(UPLOAD_FOLDER)
#     UPLOAD_FOLDER = f"{UPLOAD_FOLDER}/avatar"
#     if not os.path.exists(UPLOAD_FOLDER):
#         os.mkdir(UPLOAD_FOLDER)
#
#     upload_name = name[:10] + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.png'
#     try:
#         avinit.get_png_avatar(
#             name.strip(), output_file=f'{UPLOAD_FOLDER}/{upload_name}')
#         return f"{UPLOAD_FOLDER}/{upload_name}".replace("media/", "")
#     except Exception as e:
#         print(str(e))
#         return None

def create_avatar(name: str, which):
    s3_client = boto3.client('s3')

    upload_name = name[:10] + datetime.datetime.now().strftime("%Y%m%d%H%M%S") + '.png'

    try:
        # Generate the avatar
        avatar_file = BytesIO()
        avinit.get_png_avatar(name.strip(), output_file=avatar_file)
        avatar_file.seek(0)

        # Upload to S3
        s3_key = f"{which}/avatar/{upload_name}"
        default_storage.save(s3_key, ContentFile(avatar_file.getvalue()))

        return s3_key
    except Exception as e:
        print(str(e))
        return None


# def delete_file_in_directory(file_name):
#     try:
#         if file_name:
#             if os.path.exists(file_name):
#                 os.remove(file_name)
#     except Exception as e:
#         print(f"file delete error - file name {file_name}  error - {str(e)}")
#     return


def delete_file_in_directory(file_name):
    try:
        if file_name:
            s3_client = boto3.client('s3')
            bucket_name = settings.AWS_STORAGE_BUCKET_NAME

            # Delete the file from S3
            s3_client.delete_object(Bucket=bucket_name, Key=file_name)
            print(f"File {file_name} deleted successfully from S3.")
    except Exception as e:
        print(f"File delete error - file name {file_name} error - {str(e)}")


def get_from_token(request, key=None):
    if key:
        try:
            value = request.auth[key]
            return value
        except Exception as e:
            print("Get From Token Exception", str(e))
            pass
    return key


def get_user_profile_url(user):
    profile_url = user.memberinformation_id.profile_image.url if user.memberinformation_id.profile_image else None
    # profile_url = f'{settings.MY_DOMAIN}/{profile_url}'.replace('//media', '/media') if (
    #         profile_url and 'media' in profile_url) else profile_url
    return profile_url


def get_valid_ids_from_list(lst=None):
    if lst is None:
        lst = []
    if lst:
        return [ls for ls in lst if ls and (isinstance(ls, str) and len(replace_all_white_spaces_from_string(ls)) > 0)]
    return lst


def replace_all_white_spaces_from_string(st):
    return "".join(st.split())


def create_profile_image_by_name(first_name, last_name=None):
    if first_name and not last_name:
        profile_image = create_avatar(first_name, 'user')
    elif first_name and last_name and len(last_name) > 0:
        profile_image = create_avatar(f'{first_name} {last_name}', 'user')
    else:
        profile_image = create_avatar(first_name, 'user')
    return profile_image


def callback_action_provider(model_type, model_obj):
    ModelClass = model_obj.__class__
    if model_type == "user":
        platform_wise_users_qs = ModelClass.objects.filter(platform_id=model_obj.platform_id)
        platform_wise_users = platform_wise_users_qs.count()
        if model_obj.project_id:
            project_ids = list()
            project_id = str(get_super_parent_id(model_obj.project_id).pk)
            project_wise_qs = platform_wise_users_qs.filter(hide_user=False,
                                                            status=MEMBER_PLATFORM_ACTIVE).filter(
                project_id_id__in=get_super_parent_ids(model_obj.project_id, project_ids))
            project_wise_users = project_wise_qs.count()
            role_wise_users = project_wise_qs.values(
                'roles_id__name').annotate(count=Count('id'))
            usertype_wise_users = project_wise_qs.values('usertype_id__name').annotate(count=Count('id'))
        else:
            project_wise_users = None
            project_id = None
            role_wise_users = platform_wise_users_qs.values(
                'roles_id__name').annotate(count=Count('id'))
            usertype_wise_users = platform_wise_users_qs.values('usertype_id__name').annotate(count=Count('id'))
        user_details = {"platform_users_count": platform_wise_users, "project_users_count": project_wise_users,
                        "role_users": list(role_wise_users), "usertype_users": list(usertype_wise_users),
                        "platform_id": str(model_obj.platform_id.pk), "project_id": project_id, "type": model_type}
        return user_details
    if model_type == "project":
        platform_id = model_obj.platform_id
        platform_project_qs = ModelClass.objects.filter(platform_id=platform_id)
        platform_wise_project_count = platform_project_qs.count()
        if model_obj.parent_id:
            parent_project = get_super_parent_id(model_obj.parent_id)
        else:
            parent_project = model_obj
        children = ModelClass.objects.filter(parent_id=parent_project, status=PROJECT_ACTIVE).count()
        parent = 1
        project_details = {"platform_projects_count": platform_wise_project_count,
                           "current_project_children_count": children, "current_project_total_count": children + parent,
                           "platform_id": str(model_obj.platform_id.pk), "project_id": str(parent_project.pk),
                           "type": model_type}
        return project_details


def get_super_parent_id(project_id):
    if project_id:
        if project_id.parent_id:
            return get_super_parent_id(project_id.parent_id)
    return project_id


def get_super_parent_ids(project_id, project_ids):
    if project_id:
        project_ids.append(project_id)
        if project_id.parent_id:
            project_ids.append(project_id.parent_id.pk)
            return get_super_parent_ids(project_id.parent_id, project_ids)
    return project_ids


def callback_trigger(model_obj):
    import requests

    from usermanagement_app.models import MemberPlatform, Project, Platform, CallbackLog

    request_body = dict()

    if isinstance(model_obj, MemberPlatform):
        request_body = callback_action_provider('user', model_obj)
    elif isinstance(model_obj, Project):
        request_body = callback_action_provider('project', model_obj)

    if request_body:
        payload = json.dumps(request_body)
        platform = Platform.objects.get(pk=request_body['platform_id'])

        headers = {
            'Content-Type': 'application/json'
        }

        url = platform.crud_callback_url
        if url:
            try:
                response = requests.request('POST', url, headers=headers, data=payload)
                CallbackLog.objects.create(response_text=response.text, request_payload=request_body,
                                           response_code=response.status_code)
            except Exception as e:
                exception_message = f'Exception Message - {str(e)}'
                CallbackLog.objects.create(response_text=exception_message, request_payload=request_body,
                                           response_code=500)


def push_notification_log(**kwargs):
    from usermanagement_app.models import PushNotification, PushNotificationCount

    PushNotification.objects.create(**kwargs)

    member_platform_id = kwargs.get('member_platform_id', None)
    if member_platform_id:
        ps_qs = PushNotificationCount.objects.filter(member_platform_id=member_platform_id)
        if ps_qs.exists():
            push_notification_obj = ps_qs.first()
            push_notification_obj.count += 1
            push_notification_obj.save()


def get_name(member_information):
    name = str()
    if member_information:
        if member_information.first_name:
            name = member_information.first_name
            if member_information.last_name:
                name += f' {member_information.last_name}'
        elif member_information.last_name:
            name = member_information.last_name
    return name


class SendEmailsByProject(threading.Thread):
    def __init__(self, subject, html_message, recipients, smtp_host=None, smtp_port=None, smtp_user=None,
                 smtp_password=None, from_email=None, from_name=None):
        self.subject = subject
        self.html = html_message
        self.members = recipients
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.from_name = from_name
        threading.Thread.__init__(self)

    def run(self) -> None:
        smtp_host = self.smtp_host
        smtp_port = self.smtp_port
        smtp_user = self.smtp_user
        smtp_password = self.smtp_password
        recipients = self.members
        html_message = self.html
        try:
            print("smtp host", smtp_host)
            print("smtp port", smtp_port)
            print("smtp user", smtp_user)
            print("smtp smtp_password", smtp_password)

            for member in recipients:
                member_information = member.memberinformation_id
                msg = html_message
                msg = msg.replace('[Your Name]', get_name(member_information))
                msg = msg.replace('{{Your Name}}', get_name(member_information))
                msg = msg.replace('{{Name}}', get_name(member_information))
                msg = msg.replace('[Name]', get_name(member_information))
                if member.project_id:
                    msg = msg.replace('{{Sender signature}}', member.project_id.name)
                    msg = msg.replace('{{Sender Signature}}', member.project_id.name)
                    msg = msg.replace('{{Sender_signature}}', member.project_id.name)
                if member_information and member_information.email_id:
                    to_email = member_information.email_id
                    msg = replace_user_values_in_template(msg, memberinformation=member_information)
                    print("To email:", to_email)
                    if smtp_user and smtp_password and smtp_host and smtp_port:
                        with smtplib.SMTP(smtp_host, smtp_port) as server:
                            mime = MIMEMultipart()
                            server.starttls()
                            server.login(smtp_user, smtp_password)
                            mime['subject'] = self.subject
                            mime['to'] = str(to_email)
                            mime['from'] = str(smtp_user) if not self.from_name else self.from_name
                            mime.attach(MIMEText(msg, 'html'))
                            # Send the email
                            print("mime as string", mime.as_string())
                            server.sendmail(self.from_email, to_email, msg=mime.as_string())
                            response = server.noop()
                            if response[0] == 250:  # 250 is a success response code
                                print("Email accepted for delivery")
                                # return True
                                # delete_file_in_directory(pdf_file_name)
                            else:
                                print(f"Email not accepted. Server response: {response}")
                                # return False
                    else:
                        send_mail(
                            subject=self.subject,
                            html_message=msg,
                            from_email=self.from_email if self.from_email else settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[to_email],
                            fail_silently=False,
                            message=msg
                        )
            return
        except Exception as e:
            print(f"Error sending email: {e}")
            return


def replace_user_values_in_template(template_string, memberinformation=None, name=None, email_id=None,
                                    phone_number=None):
    from usermanagement_app.models import MemberPlatform

    if memberinformation:
        name = get_name(memberinformation)
        email_id = memberinformation.email_id

        phone_number = str()
        if memberinformation.country_code and memberinformation.phone_number:
            phone_number = f'{memberinformation.country_code} {memberinformation.phone_number}'
        elif memberinformation.phone_number:
            phone_number = memberinformation.phone_number

    if name:
        template_string = template_string.replace('${user:name}', name)
    else:
        template_string = template_string.replace('${user:name}', "User")

    if email_id:
        template_string = template_string.replace('${user:email_id}', email_id)
    else:
        template_string = template_string.replace('${user:email_id}', "-")

    if phone_number:
        template_string = template_string.replace('${user:phone_number}', phone_number)
    else:
        template_string = template_string.replace('${user:phone_number}', "-")

    if memberinformation:
        mem_platform = MemberPlatform.objects.filter(memberinformation_id=memberinformation).first()
        if mem_platform:
            project = mem_platform.project_id
            if project:
                project_name = project.name
                template_string = template_string.replace('${company:company_name}', project_name)

    return template_string


def send_password_setup_email(member_platform, magic_link="True", password_change_redirect_html_url=None):
    from usermanagement_app.models import MemberPasswordUniqueIdentifier
    from usermanagement_app.senders import OTPSendMailNotification

    if not password_change_redirect_html_url:
        password_change_redirect_html_url = f'https://app.leadcircle.ai/login/UpdateYourPassword.html'

    if member_platform:
        domain_url = member_platform.domain_url
        project_name = member_platform.platform_id.name
        member_id = member_platform.member_id

        if member_platform.project_id:
            project_name = member_platform.project_id.name
        if magic_link in ['True', 'true']:
            unique_identifier = MemberPasswordUniqueIdentifier.objects.create(
                password_redirect_url=password_change_redirect_html_url,
                domain_url=domain_url, member_id=member_id)
            if unique_identifier:
                magic_link_url = (
                    f"{password_change_redirect_html_url}?id={unique_identifier.id if unique_identifier else None}&"
                    f"member_platform_id={member_platform.id if member_platform else None}")

                member_platform.is_password_updated = True
                member_platform.save()

                OTPSendMailNotification(member_id, magic_link_url=magic_link_url, project_name=project_name,
                                        reset_password=False, template_string=None,
                                        member_platform=member_platform).start()
