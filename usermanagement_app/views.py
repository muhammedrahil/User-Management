import smtplib
import string
from datetime import timedelta

import boto3
from django.core.mail import send_mail, get_connection
from django.core.paginator import PageNotAnInteger, EmptyPage, Paginator
from django.shortcuts import redirect
import requests
from rest_framework import viewsets, status, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend

import random
import json
import firebase_admin

from firebase_admin import credentials, messaging, get_app
from USER_MANAGEMENT import settings
from usermanagement_app.pagination import StandardResultSetPagination, CustomPagination, CustomPaginationWithChildrens
from usermanagement_app.permissions import *
from usermanagement_app.senders import OTPSendMailNotification, MemberCreateMailNotification, \
    SendDefaultMailNotification, SendEmailNotification, PasswordNotification
from usermanagement_app.serializer import *
from usermanagement_app.models import *
from usermanagement_app.utils import format_platform_image_url, get_children_queryset, get_children_single_queryset, \
    get_children_single_queryset_dropdown, \
    get_memberplatform_id, get_parent, get_platform_id, get_project_id, get_request_domain, hierarchy_names, \
    is_super_platform, get_member_id, password_hash, referel_url, get_from_token, get_user_profile_url, \
    get_valid_ids_from_list, create_profile_image_by_name, push_notification_log, get_name, SendEmailsByProject, \
    send_password_setup_email
from usermanagement_app.flags import *
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.management import call_command
from rest_framework.decorators import action
from pyfcm import FCMNotification
from django.urls import reverse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# Create your views here.

@api_view(['POST'])
def super_platform_create_seeder(request):
    call_command('create_super_platform')
    return Response({"msg": "Success, Super Platform Created Successfully"}, status=status.HTTP_200_OK)


class PlatformViewSet(viewsets.ModelViewSet):
    serializer_class = PlatformSerializer
    permission_classes = (IsAuthenticated, PlatformPermitted,)
    pagination_class = StandardResultSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "Platform Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not is_super_platform(self.request):
            return Response({'msg': 'You are not a valid Platform User'}, status=status.HTTP_401_UNAUTHORIZED)
        if instance.is_super_platform:
            return Response({'msg': 'You are not able to delete the super Platform'},
                            status=status.HTTP_401_UNAUTHORIZED)
        else:
            setattr(instance, 'status', PLATFORM_DELETED)
            instance.save()
            Project.objects.filter(platform_id=instance.id, status=PROJECT_ACTIVE).update(status=PROJECT_DELETED)
            UserType.objects.filter(platform_id=instance.id, status=USERTYPE_ACTIVE).update(status=USERTYPE_DELETED)
            Roles.objects.filter(platform_id=instance.id, status=ROLE_ACTIVE).update(status=ROLE_DELETED)
            RightName.objects.filter(platform_id=instance.id, status=RIGHT_ACTIVE).update(status=RIGHT_DELETED)
            Rights.objects.filter(platform_id=instance.id, status=RIGHT_ACTIVE).update(status=RIGHT_DELETED)
            member_details_delete(request, platform_id=instance.id)
            MappedURls.objects.filter(platform_id=instance.id, status=MEMBER_ACTIVE).update(status=DELETED)
            platforms = MemberPlatform.objects.filter(platform_id=instance.id, status=MEMBER_ACTIVE)
            for platform in platforms:
                platform.memberinformation_id.status = MEMBER_INFORMATION_DELETED
                platform.memberinformation_id.save()
            platforms.update(status=MEMBER_PLATFORM_DELETE)
            return Response({'msg': 'Platform Deleted Successfully'}, status=status.HTTP_200_OK)

    def get_queryset(self):
        search = self.request.GET.get('search')
        platform_id = get_platform_id(self.request)
        if is_super_platform(self.request):
            queryset = Platform.objects.filter(status__in=[PLATFORM_ACTIVE, PLATFORM_INACTIVE]).order_by('-created_at')
        else:
            queryset = Platform.objects.filter(id=platform_id,
                                               status__in=[PLATFORM_ACTIVE, PLATFORM_INACTIVE]).order_by('-created_at')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(website__icontains=search) | Q(code__icontains=search))
        return queryset

    def create(self, request, *args, **kwargs):
        if not is_super_platform(self.request):
            return Response({'msg': 'You are not a valid Platform User'}, status=status.HTTP_401_UNAUTHORIZED)
        single_create = super().create(request, *args, **kwargs)
        domains_mapped_urls = single_create.data.get('domains_mapped') or []
        if isinstance(domains_mapped_urls, str):
            domains_mapped_urls = json.loads(domains_mapped_urls)
        for domains_mapped_url in domains_mapped_urls:
            MappedURls.objects.create(
                platform_id_id=single_create.data.get('id'),
                domain_url=domains_mapped_url,
            )
        return single_create

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "Platform Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
        MappedURls.objects.filter(platform_id_id=data.get('id'), project_id=None).delete()
        domains_mapped_urls = data.get('domains_mapped') or []
        if isinstance(domains_mapped_urls, str):
            domains_mapped_urls = json.loads(domains_mapped_urls)
        for domains_mapped_url in domains_mapped_urls:
            MappedURls.objects.create(
                platform_id_id=data.get('id'),
                domain_url=domains_mapped_url
            )
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        queryset = queryset.prefetch_related('platform_parent').filter(status=PLATFORM_ACTIVE)
        return CustomPaginationWithChildrens().get_pagination(self, request, queryset)

    def retrieve(self, request, *args, **kwargs):
        try:
            queryset = self.get_object()
        except:
            return Response({"msg": "Platform Not found."}, status=status.HTTP_404_NOT_FOUND)
        queryset_data = get_children_single_queryset(queryset, Platform, PlatformSerializer)
        queryset_data["hierarchy"] = hierarchy_names(queryset)
        return Response(queryset_data)


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "Project Not found."}, status=status.HTTP_404_NOT_FOUND)
        if not get_platform_id(self.request):
            return Response({"msg": 'The user is not mapped as a platform'}, status=status.HTTP_400_BAD_REQUEST)
        setattr(instance, 'status', PROJECT_DELETED)
        instance.save()
        UserType.objects.filter(project_id=instance.id, status=USERTYPE_ACTIVE).update(status=USERTYPE_DELETED)
        Roles.objects.filter(project_id=instance.id, status=ROLE_ACTIVE).update(status=ROLE_DELETED)
        RightName.objects.filter(project_id=instance.id, status=RIGHT_ACTIVE).update(status=RIGHT_DELETED)
        Rights.objects.filter(project_id=instance.id, status=RIGHT_ACTIVE).update(status=RIGHT_DELETED)
        member_details_delete(request, project_id=instance.id)
        platforms = MemberPlatform.objects.filter(project_id=instance.id, status=MEMBER_ACTIVE)
        for platform in platforms:
            platform.memberinformation_id.status = MEMBER_INFORMATION_DELETED
            platform.memberinformation_id.save()
        platforms.update(status=MEMBER_PLATFORM_DELETE)
        return Response({'msg': 'Project Deleted Successfully'}, status=status.HTTP_200_OK)

    def get_queryset(self):
        platform_id = get_platform_id(self.request)
        search = self.request.GET.get('search')
        if is_super_platform(self.request):
            queryset = Project.objects.filter(status__in=[PROJECT_ACTIVE, PLATFORM_INACTIVE]).order_by('-created_at')
        else:
            queryset = Project.objects.filter(platform_id=platform_id,
                                              status__in=[PROJECT_ACTIVE, PLATFORM_INACTIVE]).order_by('-created_at')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | Q(website__icontains=search) | Q(code__icontains=search))
        return queryset

    def create(self, request, *args, **kwargs):
        single_create = super().create(request, *args, **kwargs)
        domains_mapped_urls = single_create.data.get('domains_mapped') or []
        if isinstance(domains_mapped_urls, str):
            domains_mapped_urls = json.loads(domains_mapped_urls)
        for domains_mapped_url in domains_mapped_urls:
            if len(domains_mapped_url) < 200:
                MappedURls.objects.create(
                    project_id_id=single_create.data.get('id'),
                    platform_id_id=single_create.data.get('platform_id'),
                    domain_url=domains_mapped_url,
                    platform_login=False
                )
        return single_create

    def update(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "Project Not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        data = serializer.data
        MappedURls.objects.filter(project_id_id=data.get('id')).delete()
        domains_mapped_urls = data.get('domains_mapped') or []
        if isinstance(domains_mapped_urls, str):
            domains_mapped_urls = json.loads(domains_mapped_urls)
        for domains_mapped_url in domains_mapped_urls:
            MappedURls.objects.create(
                project_id_id=data.get('id'),
                platform_id_id=data.get('platform_id'),
                domain_url=domains_mapped_url,
                platform_login=False
            )
        return Response(serializer.data)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
        if project_id:
            queryset = queryset.filter(parent_id=project_id)
        # queryset = queryset.prefetch_related('project_parent').filter(status = PROJECT_ACTIVE)
        # return CustomPaginationWithChildrens().get_pagination(self, request, queryset)
        return CustomPagination().get_pagination(self, request, queryset)

    def retrieve(self, request, *args, **kwargs):
        try:
            queryset = self.get_object()
        except Exception as e:
            print("Exception of project retrieve", str(e))
            return Response({"msg": "Project Not found."}, status=status.HTTP_404_NOT_FOUND)
        child = False if request.GET.get("not_child", None) else True
        queryset_data = get_children_single_queryset(queryset, Project, ProjectSerializer, child=child)
        if child:
            queryset_data["hierarchy"] = hierarchy_names(queryset)
        return Response(queryset_data)

    @action(detail=False, methods=['get'])
    def children_list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
        if project_id:
            queryset = queryset.filter(parent_id=project_id)
        queryset = queryset.prefetch_related('project_parent').filter(status=PROJECT_ACTIVE)
        return CustomPaginationWithChildrens().get_pagination(self, request, queryset)


class LoginTokenView(APIView):

    def get(self, request, member_platform_id):
        try:
            device_id = request.GET.get('device_id', None)
            if not member_platform_id:
                return Response({"msg": "Member Platform is required"}, status=status.HTTP_400_BAD_REQUEST)
            try:
                member_platform = MemberPlatform.objects.get(id=member_platform_id)
                if member_platform:
                    member_platform.device_id = device_id
                    member_platform.save()
            except:
                return Response({"msg": "Member Platform Does not Exist"}, status=status.HTTP_400_BAD_REQUEST)
            response_token = genarate_token(member_platform, device_id)
            return Response(response_token)
        except Exception as e:
            return Response({"msg": "Login Token Retrieve Failed", 'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


def member_platform_list(member):
    member_platform = MemberPlatform.objects.filter(member_id=member, status=MEMBER_PLATFORM_ACTIVE, hide_user=False)
    if len(member_platform) > 1:
        member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platform, many=True).data
        return member_platform_login_list
    else:
        member_platform = member_platform.first()
        if member_platform:
            return genarate_token(member_platform)
    return None


def genarate_token(member_platform, device_id=None):
    member = member_platform.member_id
    memberinformation = member_platform.memberinformation_id
    usertype = member_platform.usertype_id
    platform = member_platform.platform_id
    project = member_platform.project_id
    role = member_platform.roles_id

    token = RefreshToken.for_user(member)
    token.access_token.set_exp(from_time=None, lifetime=timedelta(days=360))
    token.set_exp(from_time=None, lifetime=timedelta(days=367))
    token_items = dict()

    token_items = {"device_id": device_id}
    token_items.update({"email": member.email_id})
    token_items.update({"memberplatform_id": str(member_platform.id)})
    token_items.update({"first_name": memberinformation.first_name})
    token_items.update({"last_name": memberinformation.last_name})

    phone_number = str()
    if memberinformation.country_code:
        phone_number = memberinformation.country_code
    if memberinformation.phone_number:
        phone_number += memberinformation.phone_number

    token_items.update({"phone_number": phone_number})

    if usertype:
        token_items.update({"usertype": usertype.name})
    token_items.update({"domain_url": member_platform.domain_url})
    token_items.update({"status": member_platform.status})
    token_items.update({"role": None})
    token_items.update({"rights": []})
    if role:
        rights = role.rights_ids.values_list('name', flat=True)
        token_items.update({"role": role.name})
        token_items.update({"rights": list(rights)})

    token_items.update({"is_super_platform": platform.is_super_platform})
    token_items.update({"platform_id": str(platform.id)})
    token_items.update({"platform_name": platform.name})
    token_items.update({"platform_code": platform.code})
    token_items.update({"platform_website": platform.website})
    token_items.update({"platform_domain_url": platform.domain_url})

    token_items.update({"project_id": None})
    if project:
        # project_logo = project.logo
        project_logo = None
        if project.logo:
            project_logo = f'{project.logo.url}'
        token_items.update({"project_id": str(project.id)})
        token_items.update({"project_name": project.name})
        token_items.update({"project_code": project.code})
        token_items.update({"project_website": project.website})
        token_items.update({"project_domain_url": project.domain_url})
        token_items.update({"project_image_url": project_logo})
    for item in token_items:
        RefreshToken.__setitem__(token, item, token_items[item])

    responce_token = {}
    responce_token['access_token'] = str(token.access_token)
    responce_token['refresh_token'] = str(token)
    responce_token['token_items'] = token_items
    responce_token['is_password_updated'] = member_platform.is_password_updated
    responce_token['m_image'] = format_platform_image_url(
        f'{memberinformation.profile_image.url}') if memberinformation.profile_image else None
    return responce_token


@api_view(['POST'])
def trigger_otp(request):
    if request.method == 'POST':
        """
        Trigger OTP For user Email or Phone number which they provide.
        """
        email_id = request.data.get('email_id')
        project_name = request.data.get('project_name', None)
        if not email_id:
            return Response({'msg': "Please Provide Email Id"}, status=status.HTTP_400_BAD_REQUEST)

        member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
        if member:
            now = timezone.now()
            is_alive_otp = member.memberotp_member.filter(created_at__lt=now, expired_at__gt=now,
                                                          is_validated=False).order_by('-created_at')
            is_alive_otp_count = is_alive_otp.count()
            if is_alive_otp_count > 0:
                member_otp = is_alive_otp.first()
                member_otp.otp = random.randint(100000, 999999)
                member_otp.expired_at = get_expire_time()
                member_otp.save()
            else:
                member_otp = MemberOtp(member_id=member, otp=random.randint(100000, 999999))
                member_otp.save()
            OTPSendMailNotification(member, member_otp=member_otp, project_name=project_name).start()

            """ 
            Need to handled notification send to email or phone number
            """
            # if member.phone_number:
            #     phone_number = member.phone_number.replace("+91 ", "")
            #     # TriggerOtp(otp=otp, send_to=phone_number, member=member, template_name=template_name).start()
            # # TriggerEmailOtp(domain=domain, logo_url=logo_url, member=member, otp=otp,
            # #                 send_to=member.email_id).start()
            # #               otp=otp).start()
            return Response({'msg': 'Otp has been sent Successfully!'}, status=status.HTTP_200_OK)
        return Response({'msg': 'Member Does not Exist'}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def verify_otp(request):
    """
    Authentication Based on Otp via Email and Phone Number.
    """
    if request.method == 'POST':
        data = request.data
        otp = data.get('otp')
        email_id = data.get('email_id')
        if not email_id:
            return Response({'msg': 'Email id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not otp:
            return Response({'msg': 'OTP is required'}, status=status.HTTP_400_BAD_REQUEST)
        member_platform_id = data.get('member_platform_id')
        domain_url = data.get('domain_url', None)
        now = timezone.now()
        try:
            if member_platform_id:
                member_platform = MemberPlatform.objects.filter(id=member_platform_id,
                                                                status=MEMBER_PLATFORM_ACTIVE).first()
                member = member_platform.member_id
            else:
                member = Member.objects.filter(Q(email_id=email_id) | Q(phone_number__contains=email_id)).filter(
                    status=MEMBER_ACTIVE).get()
            if member:
                is_valid_otp = member.memberotp_member.filter(otp=otp).first()
                if not is_valid_otp:
                    return Response({'msg': 'Otp is invalid'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                if is_valid_otp.is_validated:
                    return Response({'msg': 'Otp is already used'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                if not (is_valid_otp.created_at <= now <= is_valid_otp.expired_at):
                    return Response({'msg': 'Otp is expired'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
                is_valid_otp.__dict__.update({'is_validated': True})
                is_valid_otp.save()
                """
                Redirect url function call for get the list of platform or projects mapped for the User based on 
                the that Login will Handled.
                """
                if domain_url:
                    mapped_url = MappedURls.objects.filter(domain_url__icontains=domain_url, project_id=None,
                                                           platform_login=True).first()
                    if not mapped_url:
                        return Response({
                            "msg": "Domain Urls are Emplty, So Please add Hosted domain url in Domain mapped Section for Signin"},
                            status=status.HTTP_400_BAD_REQUEST)
                    platform_id = mapped_url.platform_id
                    projects = Project.objects.filter(platform_id=platform_id, parent_id=None).values_list('id',
                                                                                                           flat=True)
                    member_platform_data = MemberPlatform.objects.filter(
                        Q(member_id=member, platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE)
                        & (Q(project_id__in=projects) | Q(project_id__isnull=True)))
                    member_platform_id_list = []
                    if member_platform_data.exists:
                        if len(member_platform_data) == 1:
                            member_platform_data_ = member_platform_data.first()
                            temp = {
                                "id": member_platform_data_.id,
                                "name": member_platform_data_.project_id.name if
                                member_platform_data_.project_id else None
                            }
                            member_platform_id_list.append(temp)
                            return Response({'msg': 'Otp verified Successfully',
                                             "member_platform_list": member_platform_id_list},
                                            status=status.HTTP_200_OK)
                        else:
                            for mem in member_platform_data:
                                temp = {
                                    "id": str(mem.id),
                                    "name": mem.project_id.name if mem.project_id else None
                                }
                                member_platform_id_list.append(temp)
                            return Response({'msg': 'Otp verified Successfully',
                                             "member_platform_list": member_platform_id_list},
                                            status=status.HTTP_200_OK)
                return Response({'msg': 'Otp verified Successfully'}, status=status.HTTP_200_OK)
            return Response({'msg': 'Member Does not Exist'}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({'msg': 'Please provide valid email information', "error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)



class RightNameViewSet(viewsets.ModelViewSet):
    serializer_class = RightNameSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name']

    def get_queryset(self):
        queryset = RightName.objects.filter(status=RIGHT_ACTIVE).order_by('-created_at')
        return queryset

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "RightName Not found."}, status=status.HTTP_404_NOT_FOUND)
        Rights.objects.filter(rightname_id=instance.id).update(status=RIGHT_DELETED)
        setattr(instance, 'status', RIGHT_DELETED)
        instance.save()
        return Response({'msg': 'RightName Deleted Successfully'}, status=status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        queryset = self.get_queryset()
        if platform_id:
            queryset = self.get_queryset().filter(platform_id=platform_id, project_id=None)
        if project_id:
            queryset = self.get_queryset().filter(project_id=project_id)
        return CustomPagination().get_pagination(self, request, queryset)


class UserTypeViewSet(viewsets.ModelViewSet):
    serializer_class = UserTypeSerializer
    pagination_class = StandardResultSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name']

    def get_queryset(self):
        queryset = UserType.objects.filter(status=USERTYPE_ACTIVE).order_by('-created_at')
        return queryset

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({'msg': "User Type Does not Exists"}, status.HTTP_400_BAD_REQUEST)
        member_platform = MemberPlatform.objects.filter(usertype_id=instance, status=MEMBER_PLATFORM_ACTIVE)
        if member_platform:
            return Response({'msg': "The User Type is already Mapped with Users,so not able to Delete."},
                            status.HTTP_400_BAD_REQUEST)
        instance.status = USERTYPE_DELETED
        instance.save()
        return Response({"msg": "User Type Deleted Successfully"}, status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        queryset = self.get_queryset()
        if platform_id:
            queryset = self.get_queryset().filter(platform_id=platform_id, project_id=None)
        if project_id:
            queryset = self.get_queryset().filter(project_id=project_id)
        return CustomPagination().get_pagination(self, request, queryset)


class RolesViewSet(viewsets.ModelViewSet):
    serializer_class = RolesSerializer
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    search_fields = ['name']

    def destroy(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except:
            return Response({"msg": "Roles Not found."}, status=status.HTTP_404_NOT_FOUND)
        member_platform = MemberPlatform.objects.filter(roles_id=instance, status=MEMBER_PLATFORM_ACTIVE)
        if member_platform:
            return Response({'msg': "The Role is already Mapped with Users,so not able to Delete."},
                            status.HTTP_400_BAD_REQUEST)
        setattr(instance, 'status', ROLE_DELETED)
        instance.save()
        return Response({'msg': 'Roles Deleted Successfully'}, status=status.HTTP_200_OK)

    def get_queryset(self):
        queryset = Roles.objects.filter(status=RIGHT_ACTIVE).order_by('-created_at')
        return queryset

    def create(self, request, *args, **kwargs):
        single_create_data = super().create(request, *args, **kwargs)
        single_create = Roles.objects.get(id=single_create_data.data['id'])
        role_rights = request.data.get('role_rights', [])
        if isinstance(role_rights, str):
            role_rights = json.loads(role_rights)
        for right_id in role_rights:
            try:
                right = Rights.objects.get(id=right_id)
                single_create.rights_ids.add(right)
            except:
                pass
        serializers = self.serializer_class(single_create).data
        return Response(serializers)

    def update(self, request, *args, **kwargs):
        single_create_data = super().update(request, *args, **kwargs)
        single_create = Roles.objects.get(id=single_create_data.data['id'])
        role_rights = request.data.get('role_rights', [])
        if isinstance(role_rights, str):
            role_rights = json.loads(role_rights)
        single_create.rights_ids.clear()
        for id in role_rights:
            try:
                right = Rights.objects.get(id=id)
                single_create.rights_ids.add(right)
            except:
                pass
        serializers = self.serializer_class(single_create).data
        return Response(serializers)

    def list(self, request, *args, **kwargs):
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        queryset = self.get_queryset()
        if platform_id:
            queryset = self.get_queryset().filter(platform_id=platform_id, project_id=None)
        if project_id:
            queryset = self.get_queryset().filter(project_id=project_id)
        return CustomPagination().get_pagination(self, request, queryset)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def member_create(request):
    if request.method == 'POST':
        platform_id, project_id, = get_platform_project_id(request)
        user_id = get_member_id(request)
        data = request.data
        company_name = None
        try:
            platform_id = Platform.objects.get(id=platform_id, status=PLATFORM_ACTIVE)
            company_name = platform_id.name.capitalize()
        except Exception as e:
            return Response({'msg': 'Platform Does not Exits, Please valid platform ID', "error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        if project_id:
            try:
                project_id = Project.objects.get(id=project_id, platform_id=platform_id, status=PROJECT_ACTIVE)
                company_name = project_id.name.capitalize()
            except Exception as e:
                return Response({'msg': 'Project Does not Exits', "error": str(e)},
                                status=status.HTTP_400_BAD_REQUEST)

        email = data.get('email_id')  # Mandatory Fields
        if not email:
            return Response({"msg": 'Email ID is required'}, status.HTTP_400_BAD_REQUEST)

        first_name = data.get('first_name')  # Mandatory Fields
        if not first_name:
            return Response({"msg": 'First Name is required'}, status.HTTP_400_BAD_REQUEST)

        role_id = data.get('role_id')
        if not role_id:
            return Response({"msg": 'Role is required'}, status.HTTP_400_BAD_REQUEST)
        role_id = Roles.objects.filter(id=role_id).first()
        if not role_id:
            return Response({"msg": 'Role does not exits,please provide valid role id'}, status.HTTP_400_BAD_REQUEST)

        usertype_id = role_id.usertype_id
        if not usertype_id:
            return Response({"msg": 'User type is required'}, status.HTTP_400_BAD_REQUEST)

        password_login = data.get('password_login', "False")
        password = data.get('password')  # Need to encrypt the password save in db
        password_decode = password
        login_url = data.get('login_url')  # Need to encrypt the password save in db

        if password_login in ['True', "true"] and not password and not login_url:
            return Response({'msg': "Please provide Password and login_url"}, status.HTTP_400_BAD_REQUEST)
        if password:
            password = password_hash(password)

        last_name = data.get('last_name')
        phone_number = data.get('phone_number')
        address_line_1 = data.get('address_line_1')
        address_line_2 = data.get('address_line_2')
        country_code = data.get('country_code')
        country = data.get('country')
        state = data.get('state')
        city = data.get('city')
        zip_code = data.get('zip_code')
        profile_image = request.FILES.get('profile_image')
        if not profile_image:
            name = first_name
            if last_name:
                name = f"{first_name}  {last_name}"
            logo_path = create_avatar(name, 'member')
            profile_image = logo_path
        member = Member.objects.filter(email_id=email).first()
        is_superuser = platform_id.is_super_platform
        if member:
            if member.status in ["2", 2]:
                return Response({"msg": "The Member is Already Deleted"}, status.HTTP_400_BAD_REQUEST)
            elif member.status in ["0", 0]:
                return Response({"msg": "The Member was Inactive"}, status.HTTP_400_BAD_REQUEST)
        else:
            member = Member.objects.create(email_id=email, is_superuser=is_superuser)

        domain_url = platform_id.domain_url
        if project_id:
            domain_url = project_id.domain_url
        is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, project_id=project_id,
                                                         member_id=member, domain_url=domain_url).first()

        if is_already_exist:
            try_to_login_name = is_already_exist.platform_id.name
            if is_already_exist.project_id:
                try_to_login_name = is_already_exist.project_id.name
            # return Response({"msg": f"Member Already Exists in {try_to_login_name}"}, status=status.HTTP_409_CONFLICT)
            return Response({"msg": f"Member Already Exists"}, status=status.HTTP_409_CONFLICT)

        member_information = MemberInformation.objects.create(first_name=first_name, last_name=last_name,
                                                              email_id=email,
                                                              phone_number=phone_number, country_code=country_code,
                                                              password=password,
                                                              address_line_1=address_line_1,
                                                              address_line_2=address_line_2,
                                                              country=country,
                                                              state=state, city=city, zip_code=zip_code,
                                                              profile_image=profile_image,
                                                              created_by=user_id)
        member_platform = MemberPlatform.objects.create(platform_id=platform_id, project_id=project_id,
                                                        member_id=member,
                                                        domain_url=domain_url,
                                                        usertype_id=usertype_id,
                                                        memberinformation_id=member_information, roles_id=role_id)
        if password_login in ['True', "true"]:
            MemberCreateMailNotification(domain_url, password_decode, member_platform, member_information, member,
                                         company_name, login_url).start()
        serializer = MemberPlatformSerializer(member_platform).data
        return Response({"msg": "Member created Successfully", "data": serializer}, status=status.HTTP_200_OK)


def get_platform_project_id(request):
    platform_id = request.data.get('platform_id')
    project_id = request.data.get('project_id')
    if not is_super_platform(request):
        platform_id = get_platform_id(request)
        if get_project_id(request):
            project_id = get_project_id(request)
    return platform_id, project_id


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def member_delete(request, member_platform_id):
    if request.method == 'DELETE':
        try:
            mem_platform = MemberPlatform.objects.filter(id=member_platform_id, status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                                            MEMBER_INFORMATION_INACTIVE]).first()
            mem_platform_len = MemberPlatform.objects.filter(member_id=mem_platform.member_id,
                                                             status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                         MEMBER_INFORMATION_INACTIVE])
            if mem_platform:
                mem_platform.status = MEMBER_PLATFORM_DELETE
                mem_platform.save()
                member_information_id = mem_platform.memberinformation_id
                member_information_id.status = MEMBER_DELETED
                member_information_id.save()

                if len(mem_platform_len) == 1:
                    mem_platform_len = mem_platform_len.first()
                    mem_platform_len.status = MEMBER_DELETED
                    mem_platform_len.save()
                return Response({'msg': 'Member Deleted Successfully'},
                                status=status.HTTP_200_OK)
            return Response({'msg': 'Member has no Member platform'},
                            status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"msg": str(e)}, status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def member_update(request, member_platform_id):
    if request.method == 'PUT':
        data = request.data
        member_platform = MemberPlatform.objects.filter(id=member_platform_id, status=MEMBER_PLATFORM_ACTIVE).first()
        if not member_platform:
            return Response({"msg": "Member Platform Does Not Exists, Please provide Valid Member Platform ID"},
                            status.HTTP_400_BAD_REQUEST)
        """
        User not able to update the email because it will mapped with many platform.
        """
        phone_number = data.get('phone_number')
        first_name = data.get('first_name')
        last_name = data.get('last_name')
        country_code = data.get('country_code')
        address_line_1 = data.get('address_line_1')
        address_line_2 = data.get('address_line_2')
        img_update = data.get('img_update', False)
        country = data.get('country')
        state = data.get('state')
        city = data.get('city')
        zip_code = data.get('zip_code')
        profile_image = request.FILES.get('profile_image')
        roles_id = data.get('role_id')
        project_id = data.get('project_id')
        if member_platform:
            memberinformation = member_platform.memberinformation_id
            memberinformation_id = MemberInformation.objects.filter(id=memberinformation.id).first()
            if first_name:
                memberinformation_id.first_name = first_name
            # if last_name:
            memberinformation_id.last_name = last_name
            if phone_number:
                memberinformation_id.phone_number = phone_number
            if country_code:
                memberinformation_id.country_code = country_code
            if address_line_1:
                memberinformation_id.address_line_1 = address_line_1
            if address_line_2:
                memberinformation_id.address_line_2 = address_line_2
            if state:
                memberinformation_id.state = state
            if city:
                memberinformation_id.city = city
            if zip_code:
                memberinformation_id.zip_code = zip_code
            if country:
                memberinformation_id.country = country
            if profile_image:
                if img_update == "true":
                    profile_image = avatar_image(profile_image, first_name, member_platform, memberinformation_id,
                                                 last_name=None)
                memberinformation_id.profile_image = profile_image
            if roles_id:
                roles_id = Roles.objects.filter(id=roles_id).first()
                if roles_id:
                    member_platform.roles_id = roles_id
                usertype_id = roles_id.usertype_id
                if usertype_id:
                    member_platform.usertype_id = usertype_id
            if project_id:
                project_id = Project.objects.filter(id=project_id).first()
                if project_id:
                    member_platform.project_id = project_id
            memberinformation_id.save()
            member_platform.save()
            serializer = MemberPlatformSerializer(member_platform).data
            return Response({'msg': "Member Updated Successfully", "data": serializer}, status.HTTP_200_OK)
        return Response({'msg': "Member Platform Does Not Exists"}, status.HTTP_400_BAD_REQUEST)


def avatar_image(profile_image, first_name, member_platform, memberinformation_id, last_name=None):
    if not profile_image:
        name = first_name
        if last_name:
            name = f"{first_name} {last_name}"
        logo_path = str(member_platform.logo.url).replace('/media', 'media')
        if memberinformation_id.name != name:
            delete_file_in_directory(logo_path)
            logo_path = create_avatar(name, 'member')
        profile_image = logo_path
        return profile_image


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def member_status_update(request, member_platform_id):
    if request.method == 'PATCH':
        status_flag = request.data.get('status')
        member_platform = MemberPlatform.objects.filter(id=member_platform_id).first()
        mem_platform_len = MemberPlatform.objects.filter(member_id=member_platform.member_id,
                                                         status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                     MEMBER_INFORMATION_INACTIVE])
        if not member_platform:
            return Response({"msg": "Member Platform Does Not Exists, Please provide Valid Member Platform ID"},
                            status.HTTP_400_BAD_REQUEST)
        if status_flag in [1, 2, 0]:
            if not member_platform.platform_id.is_super_platform:
                member_platform.status = status_flag
                member_platform.save()
                if len(mem_platform_len) == 1:
                    member_platform.member_id.status = status_flag
                    member_platform.member_id.save()
                return Response({'msg': "Member Updated Successfully"}, status=status.HTTP_200_OK)
            return Response({'msg': "Super Member cannot be Update"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': "Status Flag Doest not Exists"}, status=status.HTTP_400_BAD_REQUEST)


class MemberPlatformListAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MemberPlatformSerializer
    pagination_class = CustomPagination().get_pagination

    def get_queryset(self):
        queryset = MemberPlatform.objects.filter(
            status__in=[MEMBER_PLATFORM_ACTIVE, MEMBER_PLATFORM_INACTIVE]).order_by('-created_at')
        return queryset

    def get(self, request):
        queryset = self.get_queryset()
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        role_id = request.GET.get('role_id')
        search = request.GET.get('search')

        if is_super_platform(self.request):
            if platform_id:
                queryset = queryset.filter(platform_id=platform_id)
            if project_id and not role_id:
                queryset = queryset.filter(project_id=project_id)
            if project_id and role_id:
                queryset = queryset.filter(project_id=project_id, roles_id__id=role_id)

        else:
            platform_id = get_platform_id(self.request)
            queryset = queryset.filter(platform_id=platform_id)
            if platform_id:
                queryset = queryset.filter(platform_id=platform_id)
            if get_project_id(self.request):
                queryset = queryset.filter(project_id=get_project_id(self.request))
            elif project_id and role_id:
                queryset = queryset.filter(project_id=project_id, roles_id__id=role_id)
            else:
                if project_id and not role_id:
                    queryset = queryset.filter(project_id=project_id)
        if search:
            queryset = queryset.filter(
                Q(member_id__email_id__icontains=search) | Q(memberinformation_id__first_name__icontains=search)
                | Q(memberinformation_id__last_name__icontains=search))
        return self.pagination_class(self, request, queryset)


@api_view(['POST'])
def password_verification_by_link(request):
    """
    Update Password for user---by Magic link.
    """
    try:
        mem_info = None
        id = request.data.get('id', None)
        member_platform_id = request.data.get('member_platform_id', None)
        password = request.data.get('password', None)
        confirm_password = request.data.get('confirm_password', None)
        if not id:
            return Response({'msg': "Please Provide Id"}, status=status.HTTP_400_BAD_REQUEST)
        if not member_platform_id:
            return Response({'msg': "Please Provide member_platform_id"}, status=status.HTTP_400_BAD_REQUEST)
        is_exists = MemberPasswordUniqueIdentifier.objects.filter(id=id).first()
        if is_exists:
            member_id = is_exists.member_id.id
            password_status = is_exists.expired

            if password_status == 1 or password_status == "1":
                try:
                    member = Member.objects.filter(id=member_id, status=1).get()
                    mem_platform = MemberPlatform.objects.filter(id=member_platform_id).get()
                    if mem_platform:
                        mem_info_id = mem_platform.memberinformation_id.id
                        mem_info = MemberInformation.objects.filter(id=mem_info_id).get()

                except:
                    return Response({"msg": "Member details Not Exists"}, status.HTTP_400_BAD_REQUEST)
                if mem_info:
                    if password == confirm_password:
                        mem_info.password = password_hash(password)
                        mem_info.save()
                        is_exists.expired = VERIFICATION_INACTIVE
                        is_exists.save()
                        member_platform_list_or_token = member_platform_list(member)
                        if member_platform_list_or_token:
                            return Response(member_platform_list_or_token)
                    return Response({"msg": "Password fields didn't match."},
                                    status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response({"msg": "This link is Already used."}, status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Member unique Id Does not Exists"},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'msg': 'Please provide valid information', "error": str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def platforms_dropdown(request):
    platform_id = request.GET.get('pfid')
    queryset = Platform.objects.filter(status=USERTYPE_ACTIVE).order_by('-created_at')
    if not is_super_platform(request):
        platform_id = get_platform_id(request)
        queryset = queryset.filter(id=platform_id)
    elif platform_id:
        queryset = queryset.filter(id=platform_id)

    queryset = queryset.prefetch_related('platform_parent')
    if len(queryset) > 1:
        queryset = get_children_queryset(get_parent(queryset), queryset)
    elif len(queryset) == 1:
        queryset = get_children_single_queryset_dropdown(queryset.first(), Platform)
    return Response(queryset)


@api_view(['GET'])
def projects_dropdown(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    queryset = Project.objects.filter(status=PLATFORM_ACTIVE).order_by('-created_at')

    if is_super_platform(request):
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
    else:
        platform_id = get_platform_id(request)
        queryset = queryset.filter(platform_id=platform_id)

    if get_project_id(request):
        queryset = Project.objects.filter(id=get_project_id(request))
    else:
        if project_id:
            queryset = Project.objects.filter(id=project_id)

    queryset = queryset.prefetch_related('project_parent')
    if len(queryset) > 1:
        queryset = get_children_queryset(get_parent(queryset), queryset)
    elif len(queryset) == 1:
        queryset = get_children_single_queryset_dropdown(queryset.first(), Project)
    return Response(queryset)


@api_view(['GET'])
def user_types_dropdown(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    queryset = UserType.objects.filter(status=USERTYPE_ACTIVE).order_by('-created_at')
    if is_super_platform(request):
        if platform_id:
            queryset = UserType.objects.filter(platform_id=platform_id, project_id=None,
                                               status=USERTYPE_ACTIVE).order_by('-created_at')
    else:
        platform_id = get_platform_id(request)
        queryset = UserType.objects.filter(platform_id=platform_id, project_id=None, status=USERTYPE_ACTIVE).order_by(
            '-created_at')

    if get_project_id(request):
        project_id = Project.objects.filter(id=get_project_id(request), status=PROJECT_ACTIVE).first()
        if project_id:
            queryset = UserType.objects.filter(project_id=project_id, status=USERTYPE_ACTIVE)
    else:
        if project_id:
            project_id = Project.objects.filter(id=project_id, status=PROJECT_ACTIVE).first()
            if project_id:
                queryset = UserType.objects.filter(project_id=project_id, status=USERTYPE_ACTIVE)
    return Response(queryset.values('id', 'name'))


@api_view(['GET'])
def rights_dropdown(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    queryset = Rights.objects.filter(status=RIGHT_ACTIVE).order_by('-created_at')

    if is_super_platform(request):
        if platform_id:
            queryset = Rights.objects.filter(platform_id=platform_id, project_id=None, status=RIGHT_ACTIVE).order_by(
                '-created_at')

    else:
        platform_id = get_platform_id(request)
        queryset = Rights.objects.filter(platform_id=platform_id, project_id=None, status=RIGHT_ACTIVE).order_by(
            '-created_at')

    if get_project_id(request):
        queryset = Rights.objects.filter(project_id=get_project_id(request))
    else:
        if project_id:
            queryset = Rights.objects.filter(project_id=project_id)
    return Response(queryset.values('id', 'name'))


@api_view(['GET'])
def roles_dropdown(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    queryset = Roles.objects.filter(status=ROLE_ACTIVE).order_by('-created_at')

    if is_super_platform(request):
        if platform_id:
            queryset = Roles.objects.filter(platform_id=platform_id, project_id=None, status=ROLE_ACTIVE).order_by(
                '-created_at')

    else:
        platform_id = get_platform_id(request)
        if platform_id:
            queryset = Roles.objects.filter(platform_id=platform_id, project_id=None, status=ROLE_ACTIVE).order_by(
                '-created_at')

    if get_project_id(request):
        queryset = Roles.objects.filter(Q(project_id=get_project_id(request))).filter(status=ROLE_ACTIVE)
        return Response(queryset.values('id', 'name'))
    else:
        if project_id:
            queryset = Roles.objects.filter(Q(project_id=project_id)).filter(status=ROLE_ACTIVE)
            return Response(queryset.values('id', 'name'))
    return Response(queryset.values('id', 'name'))


@api_view(['GET'])
def members_platform_dropdown(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    queryset = MemberPlatform.objects.filter(status=ROLE_ACTIVE).order_by('-created_at')

    if is_super_platform(request):
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
    else:
        platform_id = get_platform_id(request)
        queryset = queryset.filter(platform_id=platform_id)

    if project_id:
        queryset = MemberPlatform.objects.filter(project_id=project_id, status=ROLE_ACTIVE)
    else:
        queryset = MemberPlatform.objects.filter(project_id=get_project_id(request), status=ROLE_ACTIVE)

    member_platform_ids = request.GET.get('member_platform_ids', [])
    if isinstance(member_platform_ids, str):
        member_platform_ids = get_valid_ids_from_list(json.loads(member_platform_ids))
    if member_platform_ids:
        ignore_platform_project = request.GET.get('ignore_platform_project_ids', None)
        if ignore_platform_project:
            queryset = MemberPlatform.objects.filter(pk__in=member_platform_ids)
        else:
            queryset = queryset.filter(pk__in=member_platform_ids)

    members = queryset.exclude(hide_user=True)
    members_response = list()
    for member in members:
        first_name = member.memberinformation_id.first_name if member.memberinformation_id.first_name else ""
        last_name = member.memberinformation_id.last_name if member.memberinformation_id.last_name else ""
        members_response.append({
            "id": str(member.pk),
            "memberinformation_id__first_name": first_name if first_name else "",
            "memberinformation_id__last_name": last_name if last_name else "",
            "first_name": first_name,
            "last_name": last_name,
            "profile_image": get_user_profile_url(member),
            "email_id": member.memberinformation_id.email_id,
            "designation": member.roles_id.name if member.roles_id else None
        })
    return Response(members_response)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def members_platform_dropdown_pagination(request):
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')
    search = request.GET.get('search', None)

    if not platform_id:
        platform_id = get_from_token(request, 'platform_id')
    if not project_id:
        project_id = get_from_token(request, 'project_id')

    queryset = MemberPlatform.objects.filter(status=ROLE_ACTIVE).order_by('-created_at')

    if is_super_platform(request):
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
    else:
        platform_id = get_platform_id(request)
        queryset = queryset.filter(platform_id=platform_id)

    if get_project_id(request):
        queryset = MemberPlatform.objects.filter(project_id=get_project_id(request), status=ROLE_ACTIVE)
    else:
        if project_id:
            queryset = MemberPlatform.objects.filter(project_id=project_id, status=ROLE_ACTIVE)

    if search:
        queryset = queryset.filter(Q(memberinformation_id__first_name__icontains=search) | Q(
            memberinformation_id__last_name__icontains=search) | Q(memberinformation_id__email_id=search) | Q(
            memberinformation_id__phone_number__contains=search
        ))

    members = queryset.exclude(hide_user=True)

    paginator = StandardResultSetPagination()
    paginator.page_size = request.GET.get('items_per_page', 10)
    result_page = paginator.paginate_queryset(members, request)
    paginated_data = paginator.get_paginated_dict(result_page)
    members = paginated_data['data']
    members_response = list()
    for member in members:
        first_name = member.memberinformation_id.first_name if member.memberinformation_id.first_name else ""
        last_name = member.memberinformation_id.last_name if member.memberinformation_id.last_name else ""
        members_response.append({
            "id": str(member.pk),
            "first_name": first_name,
            "last_name": last_name,
            "profile_image": get_user_profile_url(member),
            "email_id": member.memberinformation_id.email_id,
            "designation": member.roles_id.name if member.roles_id else None
        })
    paginated_data['data'] = members_response
    return Response(paginated_data, status.HTTP_200_OK)


# @api_view(['DELETE'])
# def delete_all(request):
#     Platform.objects.all().delete()
#     Project.objects.all().delete()
#     RightName.objects.all().delete()
#     Rights.objects.all().delete()
#     UserType.objects.all().delete()
#     Roles.objects.all().delete()
#     Member.objects.all().delete()
#     MemberInformation.objects.all().delete()
#     MemberPlatform.objects.all().delete()
#     MemberOtp.objects.all().delete()
#     MemberLoginActivity.objects.all().delete()
#     MailORSMS.objects.all().delete()
#     NotificationLog.objects.all().delete()
#     MemberPasswordUniqueIdentifier.objects.all().delete()
#     MappedURls.objects.all().delete()
#     return Response({"msg": "delete success fully "})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_single(request, member_platform_id):
    member_platform = MemberPlatform.objects.filter(id=member_platform_id, status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                                       MEMBER_INFORMATION_INACTIVE]).first()
    if not member_platform:
        return Response({"msg": "Member Platform Does Not Exists, Please provide Valid Member Platform ID"},
                        status.HTTP_400_BAD_REQUEST)
    member_platform_serilizer = MemberPlatformSerializer(member_platform).data
    return Response(member_platform_serilizer, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def password_update(request):
    member_platform_id = request.GET.get('mp_id')
    password = request.data.get('password')
    if not member_platform_id:
        member_platform_id = get_memberplatform_id(request)
    member_platform = MemberPlatform.objects.filter(id=member_platform_id, status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                                       MEMBER_INFORMATION_INACTIVE]).first()
    if not member_platform:
        return Response({"msg": "Member Platform Does Not Exists, Please provide Valid Member Platform ID"},
                        status.HTTP_400_BAD_REQUEST)
    if password:
        password = password_hash(password)
        member_platform.memberinformation_id.password = password
        if not member_platform.is_password_updated:
            member_platform.is_password_updated = True
            member_platform.save()
        member_platform.memberinformation_id.save()
        return Response({"msg": "Password Update Successfully"}, status=status.HTTP_200_OK)
    return Response({"msg": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def get_id_by_respective_data(request):
    domain_mapped_url = request.GET.get("domain_mapped_url")
    user_type_name = request.GET.get("user_type_name")
    role_name = request.GET.get("role_name")
    platform_id = request.GET.get("platform_id")
    try:
        respective_id = None
        if domain_mapped_url:
            platform_data = Platform.objects.filter(domains_mapped__contains=[domain_mapped_url]).get()
            if platform_data:
                respective_id = platform_data.id
        if user_type_name and not role_name:
            user_type_data = UserType.objects.filter(name=user_type_name, platform_id=platform_id,
                                                     project_id__isnull=True).get()
            if user_type_data:
                respective_id = user_type_data.id
        if role_name and user_type_name:
            role_name_data = Roles.objects.filter(name=role_name, platform_id=platform_id,
                                                  usertype_id__name=user_type_name, project_id__isnull=True).get()
            if role_name_data:
                respective_id = role_name_data.id
        return Response({"id": respective_id}, status.HTTP_200_OK)
    except Exception as e:
        return Response({'msg': "Domain url is not mapped with any Platform", "exception_msg": str(e)},
                        status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def member_sign_up(request):
    """
        This is for Lead Circle Alone.
    """
    if request.method == 'POST':
        user_id = request.auth['memberplatform_id'] if request.auth else None
        data = request.data
        platform_id = data.get('platform_id')
        project_id = data.get('project_id', None)
        device_id = data.get('device_id', None)

        try:
            platform_id = Platform.objects.get(id=platform_id, status=PLATFORM_ACTIVE)
        except Exception as e:
            return Response({'msg': 'Platform Does not Exits, Please valid platform ID', "error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)

        if project_id:
            try:
                project_id = Project.objects.get(id=project_id, platform_id=platform_id, status=PROJECT_ACTIVE)
            except Exception as e:
                return Response({'msg': 'Project Does not Exits', "error": str(e)},
                                status=status.HTTP_400_BAD_REQUEST)

        domain_url = platform_id.domain_url
        is_superuser = platform_id.is_super_platform
        if project_id:
            domain_url = project_id.domain_url

        email = data.get('email_id')  # Mandatory Fields
        if not email:
            return Response({"msg": 'Email ID is required'}, status.HTTP_400_BAD_REQUEST)

        first_name = data.get('first_name')  # Mandatory Fields
        if not first_name:
            return Response({"msg": 'First Name is required'}, status.HTTP_400_BAD_REQUEST)

        usertype_id = data.get('usertype_id')
        if not usertype_id:
            return Response({"msg": 'User type is required'}, status.HTTP_400_BAD_REQUEST)

        role_id = data.get('role_id')
        if not role_id:
            return Response({"msg": 'Role is required'}, status.HTTP_400_BAD_REQUEST)

        password_login = data.get('password_login', False)
        password = data.get('password')  # Need to encrypt the password save in db
        # if password_login and not password:
        #     return Response({'msg': "Please provide Password"}, status.HTTP_400_BAD_REQUEST)
        if password:
            password = password_hash(password)

        last_name = data.get('last_name')
        phone_number = data.get('phone_number')
        address_line_1 = data.get('address_line_1')
        address_line_2 = data.get('address_line_2')
        country_code = data.get('country_code')
        country = data.get('country')
        state = data.get('state')
        city = data.get('city')
        zip_code = data.get('zip_code')
        hide_user = data.get('hide_user', False)
        parent_project_id = data.get('parent_project_id', None)

        profile_image = request.FILES.get('profile_image')
        if not profile_image:
            if first_name:
                profile_image = create_profile_image_by_name(first_name, last_name)
            else:
                profile_image = create_profile_image_by_name(random.choice(string.ascii_uppercase),
                                                             random.choice(string.ascii_uppercase))
        member = Member.objects.filter(email_id=email).first()
        if member:
            if member.status in ["2", 2]:
                return Response({"msg": "The Member is Already Deleted"}, status.HTTP_400_BAD_REQUEST)
            elif member.status in ["0", 0]:
                return Response({"msg": "The Member was Inactive"}, status.HTTP_400_BAD_REQUEST)
            else:
                pass
        else:
            member = Member.objects.create(email_id=email, is_superuser=is_superuser)

        is_mapping = request.data.get('mapping', False)
        if is_mapping:
            is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, member_id=member,
                                                             project_id=project_id, domain_url=domain_url).first()
        else:
            is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, member_id=member).first()

        if is_already_exist:
            try_to_login_name = is_already_exist.platform_id.name
            if is_already_exist.project_id:
                try_to_login_name = is_already_exist.project_id.name
            return Response({"msg": f"Member Already Exists"}, status=status.HTTP_409_CONFLICT)

        if project_id:
            member_platform_data = MemberPlatform.objects.filter(platform_id=platform_id, member_id=member,
                                                                 project_id=None).first()
            # member_information = None
            if member_platform_data:
                member_information = MemberInformation.objects.filter(
                    pk=member_platform_data.memberinformation_id_id).first()
                member_platform_data.delete()
            else:
                existing_member_platform_data = MemberPlatform.objects.filter(platform_id=platform_id,
                                                                              member_id=member).first()
                member_information = MemberInformation.objects.filter(
                    pk=existing_member_platform_data.memberinformation_id_id).first()

            member_platform = MemberPlatform.objects.create(platform_id=platform_id, project_id=project_id,
                                                            member_id=member,
                                                            domain_url=domain_url,
                                                            memberinformation_id=member_information,
                                                            roles_id_id=role_id,
                                                            usertype_id_id=usertype_id, hide_user=hide_user,
                                                            device_id=device_id)

        else:
            member_information = MemberInformation.objects.create(first_name=first_name, last_name=last_name,
                                                                  email_id=email,
                                                                  phone_number=phone_number, country_code=country_code,
                                                                  password=password,
                                                                  address_line_1=address_line_1,
                                                                  address_line_2=address_line_2,
                                                                  country=country,
                                                                  state=state, city=city, zip_code=zip_code,
                                                                  profile_image=profile_image, )
            member_platform = MemberPlatform.objects.create(platform_id=platform_id, project_id=project_id,
                                                            member_id=member,
                                                            domain_url=domain_url,
                                                            memberinformation_id=member_information,
                                                            roles_id_id=role_id,
                                                            usertype_id_id=usertype_id, hide_user=hide_user,
                                                            device_id=device_id)
        if hide_user and parent_project_id:
            # This is to assign all the administrators in this agency or company to make them hidden users in the target
            # child project
            assign_admins_as_hidden_users(parent_project_id, project_id.pk, member_platform)
        serilizer = MemberPlatformSerializer(member_platform).data
        token_generate = None
        if member_platform:
            token_generate = genarate_token(member_platform)
        return Response({"msg": "Member created Successfully", "data": serilizer, "token": token_generate},
                        status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def member_list_without_search(request):
    member_platform = MemberPlatform.objects.filter(status=MEMBER_PLATFORM_ACTIVE).order_by('-created_at')
    platform_id = request.GET.get('pfid')
    project_id = request.GET.get('pjid')

    if is_super_platform(request):
        if platform_id:
            member_platform = member_platform.filter(platform_id=platform_id, project_id=None)
        if project_id:
            member_platform = member_platform.filter(project_id=project_id)
    else:
        platform_id = get_platform_id(request)
        member_platform = member_platform.filter(platform_id=platform_id)
        if platform_id:
            member_platform = member_platform.filter(platform_id=platform_id, project_id=None)
        if get_project_id(request):
            member_platform = member_platform.filter(project_id=get_project_id(request))
        else:
            if project_id:
                member_platform = member_platform.filter(project_id=project_id)
    serilizer = MemberPlatformSerializer(member_platform, many=True).data

    return Response(serilizer, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def projects_listed_based_on_gn_platform(request):
    platform_id = request.GET.get('platform_id', None)
    if platform_id:
        projects = Project.objects.filter(platform_id=platform_id, status=PLATFORM_ACTIVE)
    else:
        projects = Project.objects.filter(status=PLATFORM_ACTIVE)
    return Response(projects.values(), status.HTTP_200_OK)


class MemberPlatformListPerticularWaysAPIView(APIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MemberPlatformSerializer
    pagination_class = CustomPagination().get_pagination

    def get_queryset(self):
        queryset = MemberPlatform.objects.filter(
            status__in=[MEMBER_PLATFORM_ACTIVE, MEMBER_INFORMATION_INACTIVE]).order_by('-created_at')
        return queryset

    def get(self, request):
        queryset = self.get_queryset()
        platform_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        search = request.GET.get('search')

        if is_super_platform(self.request):
            if platform_id:
                queryset = queryset.filter(platform_id=platform_id)
            if project_id:
                queryset = queryset.filter(project_id=project_id)
            else:
                queryset = queryset.filter(project_id=None)
        else:
            platform_id = get_platform_id(self.request)
            queryset = queryset.filter(platform_id=platform_id)
            if platform_id:
                queryset = queryset.filter(platform_id=platform_id)
            if get_project_id(self.request):
                queryset = queryset.filter(project_id=get_project_id(self.request))
            else:
                if project_id:
                    queryset = queryset.filter(project_id=project_id)
                else:
                    queryset = queryset.filter(project_id=None)
        if search:
            queryset = queryset.filter(
                Q(member_id__email_id__icontains=search) | Q(memberinformation_id__first_name__icontains=search)
                | Q(memberinformation_id__last_name__icontains=search))
        return self.pagination_class(self, request, queryset)


class MappedURlsViewSet(viewsets.ModelViewSet):
    serializer_class = MappedURlsSerializer

    def get_queryset(self):
        platform_id = self.request.GET.get('pfid')
        project_id = self.request.GET.get('pjid')
        queryset = MappedURls.objects.filter(status__in=[ACTIVE, INACTIVE]).order_by('-created_at')
        if platform_id:
            queryset = queryset.filter(platform_id=platform_id)
        if project_id:
            queryset = queryset.filter(project_id=project_id)
        return queryset


@api_view(['POST'])
def custom_right_create(request):
    if request.method == "POST":
        rights_list = []
        name = request.data.get('name', None)
        platform_id, project_id, = get_platform_project_id(request)
        name_list = request.data.get('name_list', [])
        is_bulk_create = request.data.get('is_bulk_create', False)
        if not platform_id and not project_id:
            return Response({"please provide Platform ID or Project ID"}, status.HTTP_400_BAD_REQUEST)

        if is_bulk_create:
            if not name_list:
                return Response({'Please provide list of rights name'}, status=status.HTTP_400_BAD_REQUEST)
            right_name = RightName.objects.filter(platform_id=platform_id, project_id=project_id,
                                                  name__in=name_list).exclude(status=RIGHT_DELETED).first()
            if right_name:
                raise serializers.ValidationError({"msg": 'right name is already exists'}, code=400)
            for name in name_list:
                right_name = RightName.objects.create(platform_id_id=platform_id, project_id_id=project_id, name=name)
                right = Rights.objects.create(rightname_id=right_name, name=name, platform_id_id=platform_id,
                                              project_id_id=project_id,
                                              created_by=get_member_id(request))
                rights_list.append(str(right.id))
            return Response({'data':rights_list}, status.HTTP_200_OK)
        else:
            if not name:
                return Response({'msg':'Please provide name'}, status=status.HTTP_400_BAD_REQUEST)
            right_name = RightName.objects.filter(platform_id_id=platform_id, project_id_id=project_id,
                                                  name__iexact=name).exclude(status=RIGHT_DELETED).first()
            if right_name:
                raise serializers.ValidationError({"msg": 'right name is already exists'}, code=400)
            right_name = RightName.objects.create(platform_id_id=platform_id, project_id_id=project_id, name=name)
            Rights.objects.create(rightname_id=right_name, name=name, platform_id_id=platform_id,
                                  project_id_id=project_id,
                                  created_by=get_member_id(request))
            return Response({"msg":'Right created successfully'}, status.HTTP_200_OK)


def member_details_delete(request, platform_id=None, project_id=None):
    member_list = []
    member_info = []
    if not project_id:
        mem_data = MemberPlatform.objects.filter(platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE)
    else:
        mem_data = MemberPlatform.objects.filter(project_id=project_id, status=MEMBER_PLATFORM_ACTIVE)
    for data in mem_data:
        member_list.append(data.member_id)
        member_info.append(data.memberinformation_id.pk)
    MemberInformation.objects.filter(id__in=member_info, status=MEMBER_ACTIVE).update(
        status=MEMBER_DELETED)
    mem_data.update(status=MEMBER_PLATFORM_DELETE)
    if len(mem_data) == 1:
        Member.objects.filter(id__in=member_list, status=MEMBER_ACTIVE).update(status=MEMBER_DELETED)


@api_view(['DELETE'])
def member_details_hard_delete(request):
    mem_platform_ids = request.data.get("mem_platform_ids", [])

    if not mem_platform_ids:
        return Response({'msg': "Please provide member platform id"}, status=status.HTTP_400_BAD_REQUEST)
    mem_platform_data = MemberPlatform.objects.filter(id__in=mem_platform_ids, status=MEMBER_PLATFORM_ACTIVE)

    for mem_platform in mem_platform_data:
        mem_info = mem_platform.memberinformation_id
        member_id = mem_platform.member_id
        mem_data = mem_platform_data.count()

        MemberInformation.objects.filter(id=mem_info).delete()

        if mem_data == 1:
            Member.objects.filter(id=member_id).delete()
    mem_platform_data.delete()
    return Response({'msg': "Member platforms and associated data deleted successfully"}, status=status.HTTP_200_OK)


class LoginPasswordDomaiUrlAndGoogleAPIView(APIView):

    def post(self, request, *args, **kwargs):
        email_id = request.POST.get('email_id')
        domain_url = request.POST.get('domain_url')
        if not email_id:
            return Response({'msg': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        domain_url = referel_url(request) or domain_url
        if not domain_url:
            return Response({'msg': 'domain_url is required'}, status=status.HTTP_400_BAD_REQUEST)

        mapped_urls = MappedURls.objects.filter(domain_url__icontains=domain_url)
        if len(mapped_urls) == 0:
            return Response({'msg': f'{domain_url} domain_url Not Found'}, status=status.HTTP_400_BAD_REQUEST)
        member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
        if member:
            member_platforms = MemberPlatform.objects.filter(member_id=member, status=MEMBER_PLATFORM_ACTIVE)
            if len(member_platforms) > 0:
                if len(mapped_urls) > 1:
                    plt_list = list(set(list(mapped_urls.values_list('platform_id', flat=True))))
                    member_platforms_list = member_platforms.filter(platform_id__in=plt_list)

                    prj_list = list(set(list(mapped_urls.values_list('project_id', flat=True))))
                    prj_list = [prj for prj in prj_list if prj is not None]
                    if len(prj_list) == 0:
                        member_platforms_list = member_platforms_list.filter(project_id=None)

                    if len(member_platforms_list) == 0:
                        return Response(
                            {"msg": "Member Does not exist", 'error': 'Mapped Url Does not Mapped Member Platform'},
                            status=status.HTTP_400_BAD_REQUEST)

                    if len(member_platforms_list) == 1:
                        member_platform = member_platforms_list.first()
                        if member_platform:
                            member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platform).data
                            return Response(member_platform_login_list, status=status.HTTP_200_OK)

                    member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platforms_list,
                                                                                       many=True).data
                    return Response(member_platform_login_list, status=status.HTTP_200_OK)
                else:
                    mapped_url = mapped_urls.first()
                    platform_id = mapped_url.platform_id
                    project_id = mapped_url.project_id if mapped_url.project_id else None
                    member_platform = member_platforms.filter(platform_id=platform_id, project_id=project_id).first()
                    if member_platform:
                        member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platform).data
                        return Response(member_platform_login_list, status=status.HTTP_200_OK)
                    return Response(
                        {"msg": "Member Does not exist", 'error': 'Mapped Url Does not Mapped Member Platform'},
                        status=status.HTTP_400_BAD_REQUEST)
            return Response({"msg": "Member Does not exist", 'error': 'Member Platform Does not exist'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': 'Member Does not exist'}, status=status.HTTP_400_BAD_REQUEST)


class LoginPasswordMemberPlatformAPIView(APIView):
    def post(self, request, member_platform_id):
        password = request.POST.get('password')
        device_id = request.POST.get('device_id')
        if not password:
            return Response({'msg': 'Password is required'}, status=status.HTTP_400_BAD_REQUEST)
        member_platform = MemberPlatform.objects.filter(id=member_platform_id, status=MEMBER_PLATFORM_ACTIVE).first()
        password = password_hash(password)
        if member_platform:
            member_platform.device_id = device_id
            member_platform.save()
            member_password = member_platform.memberinformation_id.password
            if password != member_password:
                return Response({'msg': f'Password did not match'}, status=status.HTTP_400_BAD_REQUEST)
            responce_token = genarate_token(member_platform, device_id)
            return Response(responce_token, status=status.HTTP_200_OK)
        return Response({"msg": "Member Does not exist", 'error': 'Member Platform Does not exist'},
                        status=status.HTTP_400_BAD_REQUEST)


class LogoutMemberPlatformAPIView(APIView):
    def post(self, request, member_platform_id):
        member_platform = MemberPlatform.objects.filter(id=member_platform_id, status=MEMBER_PLATFORM_ACTIVE).first()

        if member_platform:
            member_platform.device_id = None
            member_platform.save()

        return Response({'msg': 'Logout successful'}, status=status.HTTP_200_OK)


@api_view(['POST'])
def member_platform_forget_password_send_to_link(request, member_platform_id):
    """
    Send Mail for forgot password to setup new password by Link.
    """
    if request.method == 'POST':
        password_change_redirect_html_url = request.data.get(
            'password_change_redirect_html_url')  # Password Rest link need to get from frontend
        magic_link = request.data.get('magic_link', "False")
        if magic_link in ['True', 'true'] and not password_change_redirect_html_url:
            return Response({'msg': "Please Provide password change redirect html url"},
                            status=status.HTTP_400_BAD_REQUEST)
        member_platform = MemberPlatform.objects.filter(id=member_platform_id, status=MEMBER_PLATFORM_ACTIVE).first()
        domain_url = member_platform.domain_url
        member_id = member_platform.member_id
        if member_platform:
            project_name = member_platform.platform_id.name
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

                    OTPSendMailNotification(member_id, magic_link_url=magic_link_url, project_name=project_name).start()

                """
                Need to Send the change password link to respective user Email ID.
                Notification  need to handled.
                """
                msg = {'msg': "Magic Link Trigger Successfully"}

            else:
                now = timezone.now()
                is_alive_otp = member_id.memberotp_member.filter(created_at__lt=now, expired_at__gt=now,
                                                                 is_validated=False).order_by('-created_at')
                is_alive_otp_count = is_alive_otp.count()
                if is_alive_otp_count > 0:
                    member_otp = is_alive_otp.first()
                    member_otp.otp = random.randint(100000, 999999)
                    member_otp.expired_at = get_expire_time()
                    member_otp.save()
                else:
                    member_otp = MemberOtp(member_id=member_id, otp=random.randint(100000, 999999))
                    member_otp.save()
                OTPSendMailNotification(member_id, member_otp=member_otp,
                                        member_platform=member_platform, project_name=project_name).start()
                msg = {'msg': "Otp Trigger to mail Successfully"}
            return Response(msg, status.HTTP_200_OK)
        return Response({'msg': "Member Platform Does Not Exists,Please provide Valid Email ID"},
                        status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def member_platform_password_verification(request):
    """
    Update Password for user after otp successfully verified.
    """
    try:
        member_platform_id = request.data.get('member_platform_id', None)
        password = request.data.get('password', None)
        confirm_password = request.data.get('confirm_password', None)
        member_platform = MemberPlatform.objects.filter(id=member_platform_id, status=MEMBER_PLATFORM_ACTIVE).first()
        if not password or not confirm_password:
            return Response({'msg': "Please Provide Password and Confirm Password."},
                            status=status.HTTP_400_BAD_REQUEST)
        if member_platform:
            try:
                mem_info = member_platform.memberinformation_id
            except:
                return Response({"msg": "Member Information Does not Exists"}, status.HTTP_400_BAD_REQUEST)
            if mem_info:
                if password == confirm_password:
                    mem_info.password = password_hash(password)
                    mem_info.save()

                    member_platform.is_password_updated = True
                    member_platform.save()
                    return Response({"msg": "Password Changed Successfully"},
                                    status=status.HTTP_200_OK)
                return Response({"msg": "Password fields didn't match."},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Member Platform Does not Exists"},
                        status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({'msg': 'Please provide valid information', "error": str(e)},
                        status=status.HTTP_400_BAD_REQUEST)


class ProjectWaysUsersDropDownList(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination

    def project_list(self, request, ):
        project_id = request.GET.get('pjid')
        platfrom_id = request.GET.get('pfid')
        if project_id:
            project_id = Project.objects.filter(id=project_id, status=PROJECT_ACTIVE).first()
            if project_id:
                queryset_list = self.get_project_children_queryset_dropdown(project_id, Project)
                return Response([queryset_list], status=status.HTTP_200_OK)
            return Response({"msg": "Project Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        if platfrom_id:
            platfrom = Platform.objects.filter(id=platfrom_id, status=PLATFORM_ACTIVE).first()
            if platfrom:
                project_querysets = Project.objects.filter(platform_id=platfrom, parent_id=None, status=PROJECT_ACTIVE)
                queryset_list = self.get_platform_project_children_queryset_dropdown(project_querysets, Project)
                return Response(queryset_list, status=status.HTTP_200_OK)
            return Response({"msg": "Platfrom Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Projects Does Not Exist, Please give any project or platform id"},
                        status=status.HTTP_400_BAD_REQUEST)

    def get_platform_project_children_queryset_dropdown(self, project_querysets: object, Model: type) -> list:
        append_list = []
        for queryset in project_querysets:
            append_dictionary = self.get_project_children_queryset_dropdown(queryset, Model)
            append_list.append(append_dictionary)
        return append_list

    def get_project_children_queryset_dropdown(self, queryset: object, Model: type) -> list:
        append_dictionary = {
            "id": str(queryset.id),
            "name": queryset.name,
            "logo": f'{queryset.logo.url}' if queryset.logo else None,
        }
        append_dictionary['children'] = self.get_project_child_single_queryset_dropdown(queryset, Model)
        return append_dictionary

    def get_project_child_single_queryset_dropdown(self, queryset: object, Model: type) -> list:
        queryset_data = []
        querysets = Model.objects.filter(parent_id=queryset)
        for queryset in querysets:
            append_dictionary = {
                "id": str(queryset.id),
                "name": queryset.name,
                "logo": f'{queryset.logo.url}' if queryset.logo else None,
            }
            append_dictionary['children'] = self.get_project_child_single_queryset_dropdown(queryset, Model)
            queryset_data.append(append_dictionary)
        return queryset_data

    def get_users_detail_params(self, request):
        project_id = request.GET.get('pjid')
        platfrom_id = request.GET.get('pfid')
        users_detail_params = request.data.get('users_details', [])
        page = int(request.GET.get('page', 1))
        search_items = request.GET.get('search')
        items_per_page = int(request.GET.get('items_per_page', 10))
        projects_list = []
        filter_values = self.filter_values(users_detail_params)
        if project_id:
            project_id = Project.objects.filter(id=project_id, status=PROJECT_ACTIVE).first()
            if project_id:
                project_querysets = self.get_project_childrens([project_id], projects_list)
                all_member_informations, page = self.get_users_list_dynamicaly(project_querysets, filter_values,
                                                                               search_items)
                # all_member_informations = self.paginate(all_member_informations, page, items_per_page)
                # return Response(all_member_informations, status=status.HTTP_200_OK)
                return page.get_paginated_response(all_member_informations)
            return Response({"msg": "Project Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        if platfrom_id:
            platfrom = Platform.objects.filter(id=platfrom_id, status=PLATFORM_ACTIVE).first()
            if platfrom:
                project_querysets = Project.objects.filter(platform_id=platfrom, parent_id=None, status=PROJECT_ACTIVE)
                project_querysets = self.get_project_childrens(project_querysets, projects_list)
                all_member_informations, page = self.get_users_list_dynamicaly(project_querysets, filter_values,
                                                                               search_items)
                # all_member_informations = self.paginate(all_member_informations, page, items_per_page)
                # return Response(all_member_informations, status=status.HTTP_200_OK)
                return page.get_paginated_response(all_member_informations)
            return Response({"msg": "Platform Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Users Does Not Exist, Please give any project or platform id"},
                        status=status.HTTP_400_BAD_REQUEST)

    def filter_values(self, users_detail_params):
        filter_values = ["id", "first_name", "last_name", "email_id", "profile_image"]
        if isinstance(users_detail_params, str):
            users_detail_params = json.loads(users_detail_params)
        for params in users_detail_params:
            if params not in ["password", "created_at", "updated_at"]:
                filter_values.append(params)
        return filter_values

    def get_project_childrens(self, project_querysets: list, projects_list: list):
        for project in project_querysets:
            projects_list.append(project)
            queryset_children = Project.objects.filter(parent_id=project, status=PROJECT_ACTIVE)
            self.get_project_childrens(queryset_children, projects_list)
        return projects_list

    def get_users_list_dynamicaly(self, querysets, filter_values: list, search_items: str) -> list:
        member_informations = []
        member_platform_list = MemberPlatform.objects.filter(project_id__in=querysets, status=MEMBER_PLATFORM_ACTIVE)
        matching_member_information = MemberInformation.objects.filter(
            memberinformation_member__in=member_platform_list)
        if search_items:
            search_filter = (
                    Q(first_name__icontains=search_items) |
                    Q(last_name__icontains=search_items) |
                    Q(email_id__icontains=search_items) |
                    Q(phone_number__icontains=search_items)
            )
            matching_member_information = matching_member_information.filter(search_filter)
        page = self.pagination_class()
        matching_member_information = page.paginate_queryset(matching_member_information, self.request)

        for mem_info in matching_member_information:
            self.add_member_information_dynamically(mem_info, member_informations, filter_values)
        return member_informations, page

    def add_member_information_dynamically(self, mem_info, member_informations, filter_values):
        member_information_dict = {}
        for field in filter_values:
            if field != "profile_image":
                data = getattr(mem_info, field, None)
                member_information_dict[field] = str(data if data else "")
            else:
                profile_image = getattr(mem_info, field, None)
                member_information_dict[field] = ""
                if profile_image:
                    member_information_dict[field] = f'{str(profile_image.url)}'
        member_informations.append(member_information_dict)
        return member_informations

    def chunked(self, iterable, chunk_size):
        for i in range(0, len(iterable), chunk_size):
            yield iterable[i:i + chunk_size]

    def paginate(self, data, page, per_page):
        datas_chunks = list(self.chunked(data, per_page))
        paginated_data = []
        if (page - 1) < len(datas_chunks):
            paginated_data = datas_chunks[(page - 1)]
        return {
            "page": page,
            "totel_page": len(datas_chunks),
            "per_page": per_page,
            "total_items": len(data),
            "data": paginated_data
        }


class MobileLogin(viewsets.ViewSet):

    def login(self, request):
        email_id = request.POST.get('email_id')
        password = request.POST.get('password')
        domain_url = request.POST.get('domain_url')
        if not domain_url:
            return Response({"msg": "Domain url is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not email_id:
            return Response({"msg": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not password:
            return Response({"msg": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)
        password = password_hash(password)
        mapped_url = MappedURls.objects.filter(domain_url__icontains=domain_url, project_id=None,
                                               platform_login=True).first()
        if not mapped_url:
            return Response(
                {"msg": "Domain Urls are Empty, So Please add Hosted domain url in Domain mapped Section for Signin"},
                status=status.HTTP_400_BAD_REQUEST)
        platform_id = mapped_url.platform_id
        projects = Project.objects.filter(platform_id=platform_id, parent_id=None).values_list('id', flat=True)
        member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
        if member:
            member_platforms = MemberPlatform.objects.filter(
                Q(member_id=member, platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE)
                & (Q(project_id__in=projects) | Q(project_id__isnull=True)))
            if len(member_platforms) > 0:
                # This is for Agency Login
                if len(member_platforms) == 1:
                    member_platform = member_platforms.first()
                    mem_info = member_platform.memberinformation_id
                    if request.data.get('device_id'):
                        member_platform.device_id = request.data.get('device_id')
                        member_platform.save()
                    if mem_info.password != password:
                        return Response({'msg': 'Password did not match'}, status=status.HTTP_400_BAD_REQUEST)
                    responce_token = genarate_token(member_platform)
                    return Response(responce_token, status=status.HTTP_200_OK)
                else:
                    password_memplatform = self.member_platfrom_password_dict(member_platforms)
                    if password in password_memplatform:
                        password_memplatform_list = password_memplatform[password]
                        if len(password_memplatform_list) > 1:
                            password_memplatform_list = member_platforms.filter(id__in=password_memplatform_list)
                            member_platform_login_list = MemberPlatformLoginListViewSerializer(
                                password_memplatform_list,
                                many=True).data
                            return Response(member_platform_login_list, status=status.HTTP_200_OK)
                        else:
                            password_memplatform = member_platforms.filter(id=password_memplatform_list[0]).first()
                            if request.data.get('device_id'):
                                password_memplatform.device_id = request.data.get('device_id')
                                password_memplatform.save()
                            responce_token = genarate_token(password_memplatform)
                            return Response(responce_token, status=status.HTTP_200_OK)
                    else:
                        return Response({'msg': f'Password did not match'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Enabling this for Client's sub company based Login
                member_platforms = MemberPlatform.objects.filter(
                    Q(member_id=member, platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE))
                if len(member_platforms) == 1:
                    member_platform = member_platforms.first()
                    mem_info = member_platform.memberinformation_id
                    if mem_info.password != password:
                        return Response({'msg': 'Password did not match'}, status=status.HTTP_400_BAD_REQUEST)
                    responce_token = genarate_token(member_platform)
                    return Response(responce_token, status=status.HTTP_200_OK)
                else:
                    password_memplatform = self.member_platfrom_password_dict(member_platforms)
                    if password in password_memplatform:
                        password_memplatform_list = password_memplatform[password]
                        if len(password_memplatform_list) > 1:
                            password_memplatform_list = member_platforms.filter(id__in=password_memplatform_list)
                            member_platform_login_list = MemberPlatformLoginListViewSerializer(
                                password_memplatform_list,
                                many=True).data
                            return Response(member_platform_login_list, status=status.HTTP_200_OK)
            return Response({"msg": "Member Does not exist", 'error': 'Member Platform Does not exist'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': 'Member Does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    def member_platfrom_password_dict(self, member_platforms):
        password_memplatform = {}
        for member_platform in member_platforms:
            member_platform_password = member_platform.memberinformation_id.password
            if member_platform_password not in password_memplatform:
                password_memplatform[member_platform_password] = []
            password_memplatform[member_platform_password].append(member_platform.id)
        return password_memplatform


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def check_old_password(request):
    member_platform_id = request.GET.get('mp_id')
    password = request.data.get('password')
    if not member_platform_id:
        member_platform_id = get_memberplatform_id(request)
    member_platform = MemberPlatform.objects.filter(id=member_platform_id, status__in=[MEMBER_PLATFORM_ACTIVE,
                                                                                       MEMBER_INFORMATION_INACTIVE]).first()
    if not member_platform:
        return Response({"msg": "Member Platform Does Not Exists, Please provide Valid Member Platform ID"},
                        status.HTTP_400_BAD_REQUEST)
    if password:
        password = password_hash(password)
        old_password = member_platform.memberinformation_id.password
        if password != old_password:
            return Response({"msg": "Incorrect Password, Please try again."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Password is correct"}, status=status.HTTP_200_OK)
    return Response({"msg": "Password is required"}, status=status.HTTP_400_BAD_REQUEST)


class ForgetPasswordforPlatformWays(viewsets.ViewSet):

    def get_email(self, request):
        email_id = request.POST.get('email_id')
        user_mapped_domain_list = request.POST.get('domain_list', "false")
        domain_url = request.POST.get('domain_url') or referel_url(request)
        password_change_redirect_html_url = request.data.get('password_change_redirect_html_url')
        if not email_id:
            return Response({"msg": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not domain_url:
            return Response({"msg": "Domain url is required"}, status=status.HTTP_400_BAD_REQUEST)
        if not user_mapped_domain_list.lower() == "true":
            if not password_change_redirect_html_url:
                return Response({"msg": "Password Change Redirect Html Url is required"},
                                status=status.HTTP_400_BAD_REQUEST)
        mapped_url = MappedURls.objects.filter(domain_url__icontains=domain_url, project_id=None,
                                               platform_login=True).first()
        if not mapped_url:
            return Response(
                {"msg": "Domain Urls are Emplty, So Please add Hosted domain url in Domain mapped Section for Signin"},
                status=status.HTTP_400_BAD_REQUEST)
        platform_id = mapped_url.platform_id
        projects = Project.objects.filter(platform_id=platform_id, parent_id=None).values_list('id', flat=True)
        member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
        if member:
            member_platforms = MemberPlatform.objects.filter(
                Q(member_id=member, platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE)
                & (Q(project_id__in=projects) | Q(project_id__isnull=True)))
            if not user_mapped_domain_list.lower() == "true":
                if len(member_platforms) > 0:
                    if len(member_platforms) == 1:
                        member_platform = member_platforms.first()
                        self.call_magik_link_api(password_change_redirect_html_url, member_platform.id)
                        return Response({"msg": "Password Link Successfully Sent"}, status=status.HTTP_200_OK)
                    else:
                        member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platforms,
                                                                                           many=True).data
                        return Response(member_platform_login_list, status=status.HTTP_200_OK)
            else:
                member_platform_login_list = MemberPlatformLoginListViewSerializer(member_platforms, many=True).data
                return Response(member_platform_login_list, status=status.HTTP_200_OK)
            return Response({"msg": "Member Does not exist", 'error': 'Member Platform Does not exist'},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({'msg': 'Member Does not exist'}, status=status.HTTP_400_BAD_REQUEST)

    def call_magik_link_api(self, password_change_redirect_html_url, member_platform_id):
        url = f'{settings.MY_DOMAIN}/api/member_platform_forget_password_send_to_link/{str(member_platform_id)}/'
        payload = {"password_change_redirect_html_url": password_change_redirect_html_url, "magic_link": "True"}
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            print("response of magik link api in success", response.text)
            return response.json()
        else:
            print("response of magik link api in failure", response.text)
        return response.text


@api_view(['POST'])
def projects_based_member_ids(request):
    """ For Lead circle project internally cal a api for provide projects ids list and get the members list."""
    if request.method == 'POST':
        projects_id = request.data.get('projects_id', '')
        if projects_id:
            project_dict = {}
            for ids in projects_id:
                mem_platform = MemberPlatform.objects.filter(project_id=ids).values_list('id', flat=True)
                if mem_platform:
                    project_dict[ids] = mem_platform
            return Response(project_dict, status=status.HTTP_200_OK)
        return Response("projects ids is empty list", status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def member_details_by_mem_platform_id(request):
    """Api for get member details by providing member platform id list"""
    member_platform_list = []
    mem_platform_list = request.data.get('mem_platform_list', [])
    mem_data = MemberPlatform.objects.filter(id__in=mem_platform_list, status=MEMBER_PLATFORM_ACTIVE)
    for data in mem_data:
        first_name = data.memberinformation_id.first_name
        last_name = data.memberinformation_id.last_name if data.memberinformation_id.last_name else None
        name = f"{first_name} {last_name}"
        data = {
            "member_platform_id": data.id,
            "name": name if last_name else first_name,
            "email": data.memberinformation_id.email_id,
            "phone_number": data.memberinformation_id.email_id if data.memberinformation_id.email_id else None
        }
        member_platform_list.append(data)
    return Response(member_platform_list, status.HTTP_200_OK)


class ListOfProjectsListBasedonProject(viewsets.ViewSet):
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination

    def get_projectsList(self, request, ):
        platfrom_id = request.GET.get('pfid')
        project_id = request.GET.get('pjid')
        search = request.GET.get("search")
        member_id = get_member_id(request)
        all_projects_list = []
        page = self.pagination_class()
        member_platforms_qs = MemberPlatform.objects.filter(member_id=member_id,
                                                            status=MEMBER_PLATFORM_ACTIVE)
        member_platforms_projects_list = member_platforms_qs.values_list('project_id', flat=True)

        if project_id:
            project_id = Project.objects.filter(id=project_id, status=PROJECT_ACTIVE).first()
            if project_id:
                parent_id = self.get_parent_project(project_id)
                self.get_all_projects_recursive([parent_id], Project, all_projects_list, str(project_id.id),
                                                member_platforms_projects_list, search=search)
                all_projects_list = page.paginate_queryset(all_projects_list, self.request)
                return page.get_paginated_response(all_projects_list)
            return Response({"msg": "Project Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        if platfrom_id:
            platfrom = Platform.objects.filter(id=platfrom_id, status=PLATFORM_ACTIVE).first()
            if platfrom:
                project_querysets = Project.objects.filter(platform_id=platfrom, parent_id=None, status=PROJECT_ACTIVE)
                self.get_all_projects_recursive(project_querysets, Project, all_projects_list,
                                                member_platforms_projects_list=member_platforms_projects_list)
                all_projects_list = page.paginate_queryset(all_projects_list, self.request)
                return page.get_paginated_response(all_projects_list)
            return Response({"msg": "Platfrom Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Projects Does Not Exist, Please give any project or platform id"},
                        status=status.HTTP_400_BAD_REQUEST)

    def get_parent_project(self, project_id):
        if project_id.parent_id:
            return self.get_parent_project(project_id.parent_id)
        return project_id

    def get_all_projects_recursive(self, project_querysets: object, Model: type, all_projects_list: list,
                                   project_id=None, member_platforms_projects_list=[], search=None) -> list:
        for queryset in project_querysets:
            all_projects_list = self.get_all_projects_recursive_children(queryset, Model, all_projects_list, project_id,
                                                                         member_platforms_projects_list, search=search)
        return all_projects_list

    def get_all_projects_recursive_children(self, queryset: object, Model: type, all_projects_list: list,
                                            project_id=None, member_platforms_projects_list=[], search=None) -> list:
        if not search and queryset.id in member_platforms_projects_list:
            append_dictionary = {
                "id": str(queryset.id),
                "name": queryset.name,
                "logo": f'{queryset.logo.url}' if queryset.logo else None,
                "website": queryset.website,
                "logged": True if project_id == str(queryset.id) else False
            }
            all_projects_list.append(append_dictionary)
        all_projects_list = self.get_project_child_single_queryset_dropdown(queryset, Model, all_projects_list,
                                                                            project_id, member_platforms_projects_list,
                                                                            search=search)
        return all_projects_list

    def get_project_child_single_queryset_dropdown(self, queryset: object, Model: type, all_projects_list: list,
                                                   project_id=None, member_platforms_projects_list=[],
                                                   search=None) -> list:
        querysets = Model.objects.filter(parent_id=queryset)
        if Model == Project and search:
            querysets = querysets.filter(name__icontains=search)

        for queryset in querysets:
            if queryset.id in member_platforms_projects_list:
                append_dictionary = {
                    "id": str(queryset.id),
                    "name": queryset.name,
                    "logo": f'{queryset.logo.url}' if queryset.logo else None,
                    "website": queryset.website,
                    "logged": True if project_id == str(queryset.id) else False
                }
                all_projects_list.append(append_dictionary)
            self.get_project_child_single_queryset_dropdown(queryset, Model, all_projects_list, project_id,
                                                            member_platforms_projects_list)
        return all_projects_list

    def get_project_based_user_token(self, request):
        project_id = request.GET.get('pjid')
        member_id = get_member_id(request)
        if not member_id:
            return Response({"msg": "Please provide Authentication Token"}, status=status.HTTP_400_BAD_REQUEST)
        if project_id:
            project_id = Project.objects.filter(id=project_id, status=PROJECT_ACTIVE).first()
            member_platform = MemberPlatform.objects.filter(project_id=project_id, member_id=member_id,
                                                            status=MEMBER_PLATFORM_ACTIVE).first()
            if member_platform:
                responce_token = genarate_token(member_platform)
                return Response(responce_token, status=status.HTTP_200_OK)
            return Response({"msg": f"Member Does Not Exist in {project_id.name} project"},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"msg": "Project Does Not Exist"}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
def memberinfo_check(request):
    """

    """
    if request.method == 'GET':
        member_platfrom_none_list = MemberPlatform.objects.filter(memberinformation_id__isnull=True).all()
        for member_platfrom_none in member_platfrom_none_list:
            member_id = member_platfrom_none.member_id
            email_id = member_id.email_id
            if email_id:
                password = password_hash('Zaigo@25')
                member_information = MemberInformation.objects.create(email_id=email_id, password=password)
                member_platfrom_none.memberinformation_id = member_information
                member_platfrom_none.save()
        return Response()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def overall_members_lists(request):
    data = []
    page = int(request.GET.get('page', 1))
    items_per_page = int(request.GET.get('items_per_page', 10))
    platform_id = request.GET.get('pfid')
    # print("platform_id",platform_id)
    project_id = request.GET.get('pjid')
    search = request.GET.get('search')

    if not is_super_platform(request):
        platform_id = get_platform_id(request)
    member_data = Member.objects.filter(status=MEMBER_ACTIVE).values_list('id', flat=True)

    if search:
        member_data = member_data.filter(email_id__icontains=search)
    for member_id in member_data:
        member_platform_data = MemberPlatform.objects.filter(member_id=member_id)
        if platform_id:
            member_platform_data = member_platform_data.filter(platform_id=platform_id)
        elif project_id:
            member_platform_data = member_platform_data.filter(project_id=project_id)
        else:
            member_platform_data = member_platform_data
        if member_platform_data:
            mem_info = member_platform_data.exclude(memberinformation_id=None).first()
            platform_data = list(
                member_platform_data.filter(project_id=None).values("id", "platform_id__id", "platform_id__name",
                                                                    "status"))
            # print('platform_data', platform_data)
            project_data = list(
                member_platform_data.exclude(project_id=None).values('id', "project_id__id", "project_id__name",
                                                                     "status"))
            # print('project_data', project_data)
            pro_pla_details = platform_data + project_data
            # print('pro_pla_details', pro_pla_details)

            data.append({"member_id": member_id,
                         "first_name": mem_info.memberinformation_id.first_name if mem_info else None,
                         "last_name": mem_info.memberinformation_id.last_name if mem_info else None,
                         "email_id": mem_info.memberinformation_id.email_id if mem_info else None,
                         "phone_number": mem_info.memberinformation_id.phone_number if mem_info else None,
                         "platform_details": pro_pla_details,
                         })
    data = paginate(data, page, items_per_page)

    return Response(data)


def chunked(iterable, chunk_size):
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i:i + chunk_size]


def paginate(data, page, per_page):
    datas_chunks = list(chunked(data, per_page))
    paginated_data = []
    next_page = None
    total_page = None
    if (page - 1) < len(datas_chunks):
        paginated_data = datas_chunks[(page - 1)]
        total_page = len(datas_chunks)
        next_page = page + 1
        if next_page >= total_page:
            next_page = None

    return {
        "page": page,
        "next_page": next_page,
        "total_page": total_page,
        "per_page": per_page,
        "total_items": len(data),
        "data": paginated_data
    }


class AppleSignIn(APIView):
    def post(self, request, *args, **kwargs):
        email_id = request.POST.get('email_id', None)
        domain_url = request.POST.get('domain_url', None)
        token = request.POST.get('token', None)
        device_id = request.POST.get('device_id', None)
        if not token:
            return Response({"msg": "token is required"}, status=status.HTTP_400_BAD_REQUEST)
        domain_url = referel_url(request) or domain_url
        if not domain_url:
            return Response({'msg': 'domain_url is required'}, status=status.HTTP_400_BAD_REQUEST)
        mapped_urls = MappedURls.objects.filter(domain_url__icontains=domain_url)
        if len(mapped_urls) == 0:
            return Response({'msg': f'{domain_url} domain_url Not Found'}, status=status.HTTP_400_BAD_REQUEST)
        member = None
        mapped_url = mapped_urls.first()
        platform_id = mapped_url.platform_id if mapped_url.platform_id else None
        project_id = mapped_url.project_id if mapped_url.project_id else None
        if email_id:
            member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
        if not email_id and token:
            member = MemberPlatform.objects.filter(apple_token=token, status=MEMBER_ACTIVE).first()
            member = member.member_id
        if member:
            member_platform = MemberPlatform.objects.filter(member_id=member, status=MEMBER_PLATFORM_ACTIVE,
                                                            platform_id=platform_id, project_id=project_id).first()
            if not member_platform:
                mem_info_create = MemberInformation.objects.create(email_id=email_id)
                member_platform = MemberPlatform.objects.create(member_id=member, apple_token=token,
                                                                memberinformation_id=mem_info_create,
                                                                platform_id=platform_id,
                                                                project_id=project_id)
        else:
            mem_create = Member.objects.create(email_id=email_id)
            mem_info_create = MemberInformation.objects.create(email_id=email_id)
            member_platform = MemberPlatform.objects.create(member_id=mem_create, apple_token=token,
                                                            memberinformation_id=mem_info_create,
                                                            platform_id=platform_id,
                                                            project_id=project_id)
        if member_platform:
            response_token = genarate_token(member_platform, device_id)
            return Response(response_token, status=status.HTTP_200_OK)
        return Response(
            {"msg": "Member Does not exist", 'error': 'Mapped Url Does not Mapped Member Platform'},
            status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
def is_role_mapped(request):
    platform = request.POST.get('platform', "False")
    domain_url = request.POST.get('domain_url')
    project = request.POST.get('project', "False")
    if domain_url:
        if platform.lower() == 'true':
            # platform_id = Platform.objects.filter(domains_mapped=domain_url).first()
            mapped_url = MappedURls.objects.filter(domain_url=domain_url, status=ACTIVE).first()
            if mapped_url:
                platform_id = mapped_url.platform_id
                role_id = Roles.objects.filter(platform_id=platform_id, status=ROLE_ACTIVE).exclude(
                    name__icontains="admin").first()
                if role_id:
                    return Response({'role_id': role_id.id, 'role_name': role_id.name}, status=status.HTTP_200_OK)
                else:
                    rights_id = Rights.objects.create(name='user', platform_id=platform_id)
                    user_type_id = UserType.objects.create(name='user', platform_id=platform_id)
                    role = Roles.objects.create(name='user', usertype_id=user_type_id, platform_id=platform_id)
                    role.rights_ids.add(rights_id)
                    return Response({'role_id': role.id, 'role_name': role.name}, status=status.HTTP_200_OK)
            else:
                return Response({"msg": "please provide valid domain url"}, status=400)
        elif project.lower() == 'true':
            # project_id = Project.objects.filter(domains_mapped=domain_url).exclude(name__icontains="admin").first()
            platform_id = None
            mapped_url = MappedURls.objects.filter(domain_url=domain_url, status=ACTIVE).first()
            if mapped_url:
                project_id = mapped_url.project_id
                platform_id = mapped_url.platform_id
                role_id = Roles.objects.filter(project_id=project_id, status=ROLE_ACTIVE).first()
                if role_id:
                    return Response({'role_id': role_id.id, 'role_name': role_id.name}, status=status.HTTP_200_OK)
                else:
                    rights_id = Rights.objects.create(name='user', project_id=project_id,
                                                      platform_id=platform_id)
                    user_type_id = UserType.objects.create(name='user', project_id=project_id,
                                                           platform_id=platform_id)
                    role = Roles.objects.create(name='user', usertype_id=user_type_id, project_id=project_id,
                                                platform_id=platform_id)
                    role.rights_ids.add(rights_id)
                    return Response({'role_id': role.id, 'role_name': role.name}, status=status.HTTP_200_OK)
            else:
                return Response({"msg": "please provide valid domain url"}, status=400)
        else:
            return Response(
                {'msg': 'Please provide the bool value for project or platform as string, it seems not !!!'},
                status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({'msg': 'Please provide domain url'}, status=status.HTTP_404_NOT_FOUND)


class PushNotificationView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):

        # fcm_server_key = settings.FCM_SERVER_KEY
        fcm_key = FcmKeys.objects.filter(platform_id=request.auth['platform_id']).order_by('-created_at').first()
        fcm_server_key = None
        if fcm_key:
            fcm_server_key = fcm_key.api_key
        if not fcm_server_key:
            return Response({"msg": "Fcm key not configured", "status": "error"}, status=status.HTTP_400_BAD_REQUEST)

        additional_message = dict()
        mail_notify = request.POST.get("mail_notify", False)
        file_name = request.POST.get("file_name")
        subject = request.POST.get("subject")
        # email = request.POST.get("email")
        email = get_from_token(request, "email")
        member_platform_id = request.POST.get("member_platform_id")
        audio_url = request.POST.get("audio_url")
        company_name = request.POST.get("company_name")
        content = request.POST.get("content")
        message = request.POST.get("message")
        message_title = request.POST.get("message_title")
        message_body = request.POST.get("message_body")
        name = f'{get_from_token(request, "first_name")} {get_from_token(request, "last_name")}'

        member_platform_obj = MemberPlatform.objects.filter(id=member_platform_id,
                                                            status=MEMBER_PLATFORM_ACTIVE).first()
        if member_platform_obj:
            registration_id = member_platform_obj.device_id
        else:
            registration_id = get_from_token(request, "device_id")

        if fcm_key:
            if fcm_key.credentials_json:
                # 1. Initialize Firebase admin sdk
                cred = credentials.Certificate(fcm_key.credentials_json.path)
                firebase_admin.initialize_app(cred)

                # 2. Send a push notification
                message = messaging.Message(
                    notification=messaging.Notification(
                        title=message_title,
                        body=message_body
                    ),
                    token=registration_id
                )

                response = messaging.send(message)

                # 3. Log the response of the push notification
                push_notification_log(registration_id=registration_id, message_title=message_title,
                                      message_body=message_body, member_platform_id_id=member_platform_id,
                                      push_notification_response=response)
                additional_message["payload"] = {"registration_id": registration_id,
                                                 "message_title": message_title,
                                                 "message_body": message_body
                                                 }
                additional_message["push_notification_response"] = response
            else:
                push_service = FCMNotification(api_key=fcm_server_key)
                # message_title = "Listen to docs"
                # message_body = f"Hi, your {file_name} audio file is ready"
                # meta_data = {"data": "success"}
                additional_message = {}
                print("message title", message_title)
                print("message body", message_body)
                print("registration id", registration_id)
                if registration_id and message_title and message_body:
                    try:
                        push_notification_response = push_service.notify_single_device(registration_id=registration_id,
                                                                                       message_title=message_title,
                                                                                       message_body=message_body)
                        PushNotification.objects.create(file_name=file_name, registration_id=registration_id,
                                                        message=message,
                                                        message_body=message_body,
                                                        member_platform_id_id=member_platform_id,
                                                        message_title=message_title, content=content,
                                                        audio_url=audio_url,
                                                        push_notification_response=push_notification_response)
                        additional_message["payload"] = {"registration_id": registration_id,
                                                         "message_title": message_title,
                                                         "message_body": message_body
                                                         }
                        additional_message["push_notification_response"] = push_notification_response
                        ps_qs = PushNotificationCount.objects.filter(member_platform_id=member_platform_id)
                        if ps_qs.exists():
                            push_notification_obj = ps_qs.first()
                            push_notification_obj.count += 1
                            push_notification_obj.save()
                    except Exception as e:
                        additional_message["exception_message"] = str(e)
        else:
            PushNotification.objects.create(file_name=file_name, registration_id=registration_id, message=message,
                                            message_body=message_body, member_platform_id_id=member_platform_id,
                                            message_title=message_title, content=content, audio_url=audio_url,
                                            push_notification_response={"msg": "push notification failed"})
            return Response({"msg": "push notification msg - Insufficient Data"}, status=status.HTTP_400_BAD_REQUEST)
        if mail_notify in ["True", True] and email and audio_url:
            SendDefaultMailNotification(subject, email, message, member_platform_id, audio_url, company_name,
                                        content).start()
        else:
            return Response({"msg": "email notification msg - Insufficient Data"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"msg": "notify success", "additional_message": additional_message}, status=status.HTTP_200_OK)


class PushNotificationHistoryViewSet(viewsets.ModelViewSet):
    serializer_class = PushNotificationSerializer
    # queryset = PushNotification.objects.all()
    permission_classes = (IsAuthenticated, PlatformPermitted,)

    def get_queryset(self):
        request = self.request
        member_platform_id = get_from_token(request, "memberplatform_id")
        ps_qs = PushNotificationCount.objects.filter(member_platform_id=member_platform_id)
        if ps_qs.exists():
            push_notification_obj = ps_qs.first()
            push_notification_obj.count = 0
            push_notification_obj.save()
        return PushNotification.objects.filter(member_platform_id_id=member_platform_id).order_by('-created_at')


class FcmKeysViewSet(viewsets.ModelViewSet):
    serializer_class = FcmKeysSerializer
    queryset = FcmKeys.objects.all()
    permission_classes = (IsAuthenticated,)


@api_view(['POST'])
def member_registration_without_token(request):
    if request.method == 'POST':
        data = request.data
        platform_id = None
        project_id = None
        domain_url = data.get('domain_url')
        device_id = data.get('device_id')
        if not domain_url:
            return Response({"msg": "please provide domain url"}, status=400)
        company_name = None
        mapped_url = MappedURls.objects.filter(domain_url=domain_url).first()
        if mapped_url:
            platform_id = mapped_url.platform_id.id if mapped_url.platform_id else None
            project_id = mapped_url.project_id.id if mapped_url.project_id else None
        try:
            platform_id = Platform.objects.get(id=platform_id, status=PLATFORM_ACTIVE)
            company_name = platform_id.name.capitalize()
        except Exception as e:
            return Response({'msg': 'Platform Does not Exits, Please valid platform ID', "error": str(e)},
                            status=status.HTTP_400_BAD_REQUEST)
        if project_id:
            try:
                project_id = Project.objects.get(id=project_id, platform_id=platform_id, status=PROJECT_ACTIVE)
                company_name = project_id.name.capitalize()
            except Exception as e:
                return Response({'msg': 'Project Does not Exits', "error": str(e)},
                                status=status.HTTP_400_BAD_REQUEST)

        email = data.get('email_id')  # Mandatory Fields
        if not email:
            return Response({"msg": 'Email ID is required'}, status.HTTP_400_BAD_REQUEST)

        first_name = data.get('first_name')  # Mandatory Fields
        if not first_name:
            return Response({"msg": 'First Name is required'}, status.HTTP_400_BAD_REQUEST)

        role_id = Roles.objects.filter(platform_id=platform_id, status=ROLE_ACTIVE, name='user').first()
        if not role_id:
            rights_id = Rights.objects.create(name='user', platform_id=platform_id)
            user_type_id = UserType.objects.create(name='user', platform_id=platform_id)
            role_id = Roles.objects.create(name='user', usertype_id=user_type_id, platform_id=platform_id)
            role_id.rights_ids.add(rights_id)

        usertype_id = role_id.usertype_id
        if not usertype_id:
            return Response({"msg": 'User type is required'}, status.HTTP_400_BAD_REQUEST)

        password_login = data.get('password_login', "False")
        password = data.get('password')  # Need to encrypt the password save in db
        password_decode = password
        login_url = data.get('login_url')  # Need to encrypt the password save in db

        if password_login in ['True', "true"] and not password and not login_url:
            return Response({'msg': "Please provide Password and login_url"}, status.HTTP_400_BAD_REQUEST)
        if password:
            password = password_hash(password)

        last_name = data.get('last_name')
        phone_number = data.get('phone_number')
        address_line_1 = data.get('address_line_1')
        address_line_2 = data.get('address_line_2')
        country_code = data.get('country_code')
        country = data.get('country')
        state = data.get('state')
        city = data.get('city')
        zip_code = data.get('zip_code')
        profile_image = request.FILES.get('profile_image')
        if not profile_image:
            name = first_name
            if last_name:
                name = f"{first_name}  {last_name}"
            logo_path = create_avatar(name, 'member')
            profile_image = logo_path
        member = Member.objects.filter(email_id=email).first()
        is_superuser = platform_id.is_super_platform
        if member:
            if member.status in ["2", 2]:
                return Response({"msg": "The Member is Already Deleted"}, status.HTTP_400_BAD_REQUEST)
            elif member.status in ["0", 0]:
                return Response({"msg": "The Member was Inactive"}, status.HTTP_400_BAD_REQUEST)
        else:
            member = Member.objects.create(email_id=email, is_superuser=is_superuser)

        domain_url = platform_id.domain_url
        if project_id:
            domain_url = project_id.domain_url
        is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, project_id=project_id,
                                                         member_id=member, domain_url=domain_url).first()

        if is_already_exist:
            try_to_login_name = is_already_exist.platform_id.name
            if is_already_exist.project_id:
                try_to_login_name = is_already_exist.project_id.name
            return Response({"msg": f"Member Already Exists"}, status=status.HTTP_409_CONFLICT)

        member_information = MemberInformation.objects.create(first_name=first_name, last_name=last_name,
                                                              email_id=email,
                                                              phone_number=phone_number, country_code=country_code,
                                                              password=password,
                                                              address_line_1=address_line_1,
                                                              address_line_2=address_line_2,
                                                              country=country,
                                                              state=state, city=city, zip_code=zip_code,
                                                              profile_image=profile_image)
        member_platform = MemberPlatform.objects.create(platform_id=platform_id, project_id=project_id,
                                                        member_id=member,
                                                        domain_url=domain_url,
                                                        usertype_id=usertype_id,
                                                        memberinformation_id=member_information, roles_id=role_id,
                                                        device_id=device_id)
        if password_login in ['True', "true"]:
            MemberCreateMailNotification(domain_url, password_decode, member_platform, member,
                                         company_name, login_url).start()
        # serializer = MemberPlatformSerializer(member_platform).data
        response_token = genarate_token(member_platform, device_id)
        return Response(response_token)


class SendEmail(APIView):

    def post(self, request, *args, **kwargs):
        subject = request.data.get('subject')
        email = request.data.get('email')
        message = request.data.get('message')
        company_name = request.data.get('platform_name', None)
        member_platform_id = request.data.get('member_platform_id')
        name = email
        platform_logo = None
        if member_platform_id:
            try:
                member = MemberPlatform.objects.get(pk=member_platform_id)
                member_information = member.memberinformation_id

                if member_information.first_name:
                    name = member_information.first_name
                    if member_information.last_name:
                        name += f' {member_information.last_name}'
                elif member_information.last_name:
                    name = member_information.last_name
                # name = f'{member_information.first_name} {member_information.last_name}'
                platform_logo = member.platform_id.logo.url
                email = member_information.email_id
            except Exception as e:
                name = email
        template_name = request.data.get('template_name', "payment_success")

        SendEmailNotification(subject, email, name, message, template_name, company_name, request,
                              platform_logo).start()
        return Response({"msg": "Email has been sent"}, status.HTTP_200_OK)
        # SendDefaultMailNotification(subject, email, message, member_platform_id, audio_url, company_name,
        #                             content).start()


class Users(APIView):
    permission_classes = (IsAuthenticated,)
    pagination_class = StandardResultSetPagination

    def get(self, request, *args, **kwargs):
        # Get Platform and Project ID From Token
        platform_id = get_from_token(request, "platform_id")
        project_id = get_from_token(request, "project_id")
        member_platform_id = get_from_token(request, "memberplatform_id")

        # Query Params retrieval
        search = request.GET.get("search", None)
        requested_project_id = request.GET.get("project_id", None)

        # Get Users information based on project and platform
        users = MemberPlatform.objects.select_related('memberinformation_id', 'platform_id',
                                                      'project_id').filter(
            platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE).exclude(hide_user=True)
        if requested_project_id:
            users = users.filter(project_id_id=requested_project_id)
        elif project_id:
            users = users.filter(project_id_id=project_id)
        # Search from Query Params
        if search:
            users = users.filter(Q(memberinformation_id__first_name__icontains=search) |
                                 Q(memberinformation_id__last_name__icontains=search) |
                                 Q(memberinformation_id__email_id=search) |
                                 Q(memberinformation_id__phone_number=search)
                                 )
        page = self.pagination_class()
        users_paginated_data = page.paginate_queryset(queryset=users, request=request)
        users_paginated_dict = page.get_paginated_dict(users_paginated_data)
        users_qs = users_paginated_dict.get('data', [])
        if users_qs:
            users_paginated_dict['data'] = self.get_users_list(users_qs=users_qs, member_platform_id=member_platform_id)
        return Response(users_paginated_dict, status.HTTP_200_OK)

    def get_users_list(self, users_qs=None, user_obj=None, member_platform_id=None):
        users_list = []
        if users_qs:
            for user in users_qs:
                users_list.append(self.get_user_dict(user, member_platform_id))
        if user_obj:
            return self.get_user_dict(user_obj, member_platform_id)
        return users_list

    def get_user_dict(self, user, member_platform_id=None):
        user_id = str(user.pk)
        profile_url = get_user_profile_url(user)
        # profile_url = user.memberinformation_id.profile_image.url if user.memberinformation_id.profile_image else None
        # profile_url = f'{settings.MY_DOMAIN}/{profile_url}'.replace('//media', '/media') if (
        #         profile_url and 'media' in profile_url) else profile_url
        user_dict = {
            "id": user_id,
            "first_name": user.memberinformation_id.first_name,
            "last_name": user.memberinformation_id.last_name,
            "email_id": user.memberinformation_id.email_id,
            "phone_number": user.memberinformation_id.phone_number,
            "country_code": user.memberinformation_id.country_code,
            "company_name": user.project_id.name,
            "agency_name": user.project_id.name,
            "client_name": user.project_id.name,
            "project_id": str(user.project_id_id),
            "role_name": user.roles_id.name,
            "user_type_name": str(user.usertype_id.name),
            "is_logged_in": False,
            "profile_image": profile_url
        }
        if member_platform_id and user_id == member_platform_id:
            user_dict['is_logged_in'] = True
        return user_dict

    @staticmethod
    def get_member_object(email_id, phone_number, first_name, last_name):
        try:
            if phone_number and len(phone_number) > 0:
                member = Member.objects.get(Q(email_id=email_id) | Q(phone_number=phone_number))
            else:
                member = Member.objects.get(email_id=email_id)
        except Exception as e:
            if isinstance(phone_number, str) and (len(phone_number) == 0 or len("".join(phone_number.split())) == 0):
                phone_number = None
            member = Member.objects.create(email_id=email_id, phone_number=phone_number, first_name=first_name,
                                           last_name=last_name)
        return member

    @staticmethod
    def get_domain_url(project_qs, platform_id):
        if project_qs:
            project = project_qs.first()
            domain_url = project.domain_url
        else:
            try:
                domain_url = Platform.objects.get(pk=platform_id).domain_url
            except Exception as e:
                domain_url = None
        return domain_url

    @staticmethod
    def form_response(message, key, status):
        return Response({"msg": message, key: message}, status)


def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))


class CreateUsers(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        # Get Platform and Project ID from token
        platform_id = get_from_token(request, "platform_id")
        project_id = get_from_token(request, "project_id")

        # Get from request post body
        email_id = request.data.get("email_id", None)
        first_name = request.data.get("first_name", None)
        last_name = request.data.get("last_name", None)
        phone_number = request.data.get("phone_number", None)
        country_code = request.data.get("country_code", None)
        request_project_id = request.data.get("project_id", None)
        address_line_1 = request.data.get('address_line_1')
        address_line_2 = request.data.get('address_line_2')
        country = request.data.get('country')
        state = request.data.get('state')
        city = request.data.get('city')
        zip_code = request.data.get('zip_code')
        profile_image = request.FILES.get('profile_image')
        password = request.data.get('password', None)
        is_super_admin = request.data.get('is_super_admin', False)
        role_id = request.data.get('role_id', None)
        hide_user = request.data.get('hide_user', False)

        # Password Generation
        # if password:
        #     password = password_hash(password)
        # else:
        #     password = password_hash("LD_Ld*!E")
        random_password = generate_random_password(8)
        password = password_hash(random_password)
        # Get Project obj and project ID
        project_qs = Project.objects.filter(pk=request_project_id, platform_id=platform_id)

        if request_project_id and project_qs.exists():
            project_id = request_project_id

        # Validations
        if not email_id:
            return Users.form_response("Email ID is required", "email_id", status.HTTP_400_BAD_REQUEST)

        if not first_name:
            return Users.form_response("First Name is required", "first_name", status.HTTP_400_BAD_REQUEST)

        if phone_number and len(phone_number) > 18:
            return Users.form_response(f"Phone Number should not exceeds than 18 digits", "first_name",
                                       status.HTTP_400_BAD_REQUEST)

        if country_code and len(country_code) > 6:
            return Users.form_response("Country code invalid", "country_code", status.HTTP_400_BAD_REQUEST)

        # Get Domain url and Member Object
        domain_url = Users.get_domain_url(project_qs, platform_id)
        member = Users.get_member_object(email_id, phone_number, first_name, last_name)

        # Member Status based validation
        if member.status in ["2", 2]:
            return Users.form_response("The Member is Already Deleted", "email_id", status.HTTP_400_BAD_REQUEST)
        elif member.status in ["0", 0]:
            return Users.form_response("Member is Inactive already", "email_id", status.HTTP_400_BAD_REQUEST)

        # Check if duplicate account creation attempt
        if not hide_user:
            is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, member_id=member).first()
        else:
            is_already_exist = MemberPlatform.objects.filter(platform_id=platform_id, member_id=member,
                                                             project_id=project_id, domain_url=domain_url).first()
        if is_already_exist:
            if email_id == is_already_exist.memberinformation_id.email_id:
                key = "email_id"
                message = "Email Id already taken"
            else:
                key = "phone_number"
                message = "Phone Number already taken"
            return Users.form_response(message, key, status.HTTP_400_BAD_REQUEST)
        else:
            # Check if User type exists, If not create one.
            user_type_qs = UserType.objects.filter(
                Q(Q(project_id=project_id) | Q(platform_id=platform_id))
                & Q(name__in=["Tenant Administrator", "Tenant Administrators"])
            )
            if user_type_qs.exists():
                user_type_id = user_type_qs.first().pk
            else:
                user_type = UserType.objects.create(platform_id=platform_id, name="Tenant Administrator")
                user_type_id = user_type.pk

            # Check if Role exists, If not create one.
            if not role_id:
                role = Roles.objects.filter(
                    Q(Q(project_id=project_id) | Q(platform_id=platform_id)) & Q(name="Tenant User"))
                if role.exists():
                    role_id = role.first().pk
                else:
                    role = Roles.objects.create(platform_id=platform_id, name="Tenant User",
                                                user_type_id_id=user_type_id)
                    role_id = role.pk

            if not profile_image:
                if first_name:
                    profile_image = create_profile_image_by_name(first_name, last_name)
                else:
                    profile_image = create_profile_image_by_name(random.choice(string.ascii_uppercase),
                                                                 random.choice(string.ascii_uppercase))
                # if first_name and not last_name:
                #     profile_image = create_avatar(first_name, 'user')
                # elif first_name and last_name and len(last_name) > 0:
                #     profile_image = create_avatar(f'{first_name} {last_name}', 'user')
                # else:
                #     profile_image = create_avatar(first_name, 'user')

            # Finally creat User Member Platform and Member information
            member_information = MemberInformation.objects.create(first_name=first_name, last_name=last_name,
                                                                  email_id=email_id,
                                                                  phone_number=phone_number, country_code=country_code,
                                                                  password=password,
                                                                  address_line_1=address_line_1,
                                                                  address_line_2=address_line_2,
                                                                  country=country,
                                                                  state=state, city=city, zip_code=zip_code,
                                                                  profile_image=profile_image)
            member_platform = MemberPlatform.objects.create(platform_id_id=platform_id,
                                                            project_id_id=project_id,
                                                            member_id=member, domain_url=domain_url,
                                                            roles_id_id=role_id,
                                                            usertype_id_id=user_type_id,
                                                            is_super_admin=is_super_admin,
                                                            memberinformation_id=member_information,
                                                            is_password_updated=False,
                                                            hide_user=hide_user
                                                            )

            # PasswordNotification(member, random_password).start()
            send_password_setup_email(member_platform)
            # Serialize the member platform information
            serializer = MemberPlatformSerializer(member_platform).data
            return Response({"msg": "User Created Successfully", "data": serializer}, status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_pushnotification_count(request):
    member_platform_id = get_from_token(request, "memberplatform_id")
    ps_qs = PushNotificationCount.objects.filter(member_platform_id=member_platform_id)
    if ps_qs.exists():
        push_notification_count_obj = ps_qs.first()
        ps_count = push_notification_count_obj.count
    else:
        ps_obj = PushNotificationCount.objects.create(member_platform_id_id=member_platform_id)
        ps_count = ps_obj.count
    return Response({"notification_count": ps_count}, status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_user(_, member_platform_id, target_project_id):
    try:
        member_platform = MemberPlatform.objects.get(pk=member_platform_id)
    except Exception as e:
        return Response({"msg": "Invalid User Info", "exception_msg": str(e)}, status.HTTP_400_BAD_REQUEST)

    try:
        if MemberPlatform.objects.filter(member_id=member_platform.member_id, project_id_id=target_project_id).exists():
            return Response({"msg": "User already assigned to this client"}, status.HTTP_400_BAD_REQUEST)
        else:
            member_platform.pk = None
            member_platform.project_id_id = target_project_id
            member_platform_obj = member_platform.save()

            member_information = member_platform_obj.memberinformation_id
            if member_information:
                member_information.pk = None
                member_information_obj = member_information.save()
                member_platform_obj.memberinformation_id = member_information_obj
                member_platform_obj.save()

    except Exception as e:
        return Response({"msg": "Error occured while assigning", "exception_msg": str(e)}, status.HTTP_400_BAD_REQUEST)

    return Response({"msg": "User Assigned Successfully"}, status.HTTP_200_OK)


def assign_admins_as_hidden_users(parent_project_id, target_project_id, exclude_member_platform=None):
    if exclude_member_platform and exclude_member_platform.memberinformation_id:
        email_id = exclude_member_platform.memberinformation_id.email_id
        member_platforms = MemberPlatform.objects.filter(project_id=parent_project_id, roles_id__name__contains="Admin",
                                                         usertype_id__name__in=[
                                                             "Tenant Admin", "Tenant Administrators",
                                                             "Tenant Administrator"
                                                         ]).exclude(memberinformation_id__email_id=email_id).values()
        for member_platform in member_platforms:
            member_platform_dict = dict(member_platform)
            member_platform_dict.pop('id')
            member_platform_dict['project_id_id'] = target_project_id
            member_platform_dict['hide_user'] = True
            mp = MemberPlatform.objects.create(**member_platform_dict)

            if mp.memberinformation_id:
                member_information_qs = MemberInformation.objects.filter(pk=mp.memberinformation_id.pk)
                member_information_dict = dict(member_information_qs.values()[0])
                member_information_dict.pop('id')
                member_information = MemberInformation.objects.create(**member_information_dict)
                if member_information:
                    mp.memberinformation_id_id = member_information.pk
                    mp.save()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def roles_list_dropdown(request):
    filter_params = {"status": ROLE_ACTIVE}

    platform_id = request.GET.get('platform_id')
    if not platform_id:
        platform_id = get_from_token(request, 'platform_id')
        filter_params['platform_id'] = platform_id

    project_id = request.GET.get('project_id')
    if not project_id:
        project_id = get_from_token(request, 'project_id')
    if project_id:
        filter_params['project_id'] = project_id

    roles_qs = Roles.objects.filter(**filter_params)
    if roles_qs.exists():
        roles = roles_qs.values('id', 'name')
    else:
        user_type_qs = UserType.objects.filter(
            Q(Q(project_id=project_id) | Q(platform_id=platform_id))
            & Q(name__in=["Tenant Administrator", "Tenant Administrators"])
        )
        if user_type_qs.exists():
            user_type_id = user_type_qs.first().pk
        else:
            user_type = UserType.objects.create(platform_id=platform_id, name="Tenant Administrator")
            user_type_id = user_type.pk
        roles_name = ["Tenant Admin", "Tenant User"]
        for role_name in roles_name:
            Roles.objects.create(name=role_name, platform_id_id=platform_id, project_id_id=project_id,
                                 usertype_id_id=user_type_id)
        roles = Roles.objects.filter(platform_id=platform_id, project_id=project_id).values('id', 'name')
    for role in roles:
        if role['name'] == "Tenant Admin":
            role['name'] = "Admin"
        elif role['name'] == "Tenant User":
            role['name'] = "User"
    return Response(roles, status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_admin_account(request):
    project_id = get_from_token(request, 'project_id')
    try:
        project = Project.objects.get(pk=project_id)
    except Exception as e:
        return Response({"status": "failure", "msg": "No project found", "exception_message": str(e)},
                        status.HTTP_400_BAD_REQUEST)
    qs = MemberPlatform.objects.filter(project_id=project, hide_user=False, usertype_id__name__contains="Admin",
                                       roles_id__name__contains="Admin")
    if not qs.exists():
        qs = MemberPlatform.objects.filter(project_id=project, hide_user=False, usertype_id__name__contains="Admin")

    if qs.exists():
        member_platform = qs.first()
        if member_platform.memberinformation_id:
            response = {
                "email_id": member_platform.memberinformation_id.email_id,
                "first_name": member_platform.memberinformation_id.first_name,
                "last_name": member_platform.memberinformation_id.last_name,
            }
            return Response(response, status.HTTP_200_OK)
        return Response({}, status.HTTP_200_OK)
    return Response({}, status.HTTP_200_OK)


@api_view(['POST'])
def send_push_notification_for_all_users(request, project_id):
    sound = request.data.get('sound', True)
    vibrate = request.data.get('vibrate', False)

    title = request.data.get('title', None)
    if not title:
        return Response({"status": "failure", "msg": "Please provide title"}, status.HTTP_400_BAD_REQUEST)

    description = request.data.get('description', None)
    if not description:
        return Response({"status": "failure", "msg": "Please provide message"}, status.HTTP_400_BAD_REQUEST)

    try:
        project = Project.objects.get(pk=project_id)
    except Exception as e:
        return Response({"status": "failure", "msg": f'Failed due to- {str(e)}'}, status.HTTP_400_BAD_REQUEST)

    fcm_key = FcmKeys.objects.filter(platform_id=project.platform_id).order_by('-created_at').first()
    if not fcm_key:
        return Response({"status": "failure", "msg": "Fcm key not configured"}, status.HTTP_400_BAD_REQUEST)

    members = MemberPlatform.objects.filter(status=MEMBER_PLATFORM_ACTIVE, hide_user=False, project_id=project)
    if members.exists():
        app_name = f'LC_{project_id}'
        try:
            app = get_app(app_name)
        except Exception as e:
            file_name = fcm_key.credentials_json.name
            file_dict = get_s3_file_json(file_name)
            # 1. Initialize Firebase admin sdk
            cred = credentials.Certificate(file_dict)
            app = firebase_admin.initialize_app(cred, name=app_name)
            print(f"app already initialized exception - {str(e)}")

        tokens = [member.device_id for member in members if member.device_id]

        if not tokens:
            return Response({"status": "success", "msg": "Device Tokens not there"}, status.HTTP_200_OK)

        msg_params = {
            "notification": messaging.Notification(
                title=title,
                body=description
            ),
            "tokens": tokens,
            "data": {"id": request.data.get('data_id')},
        }

        if vibrate and sound:
            channel_id = 'dual'
            sound = True
        elif sound and not vibrate:
            channel_id = 'sound'
            sound = True
        elif vibrate and not sound:
            channel_id = 'vibration'
            sound = False
        else:
            channel_id = 'silent'
            sound = False

        if vibrate:
            # msg_params["android"] = messaging.AndroidNotification(channel_id=channel_id)
            msg_params["android"] = messaging.AndroidConfig(
                notification=messaging.AndroidNotification(channel_id=channel_id))
            msg_params["apns"] = messaging.APNSConfig(payload=messaging.APNSPayload(messaging.Aps(
                sound=messaging.CriticalSound(name="default", critical=sound))))
            # msg_params["apns"] = messaging.APNSConfig(messaging.Aps(sound=sound))

        message = messaging.MulticastMessage(**msg_params)
        response = messaging.send_each_for_multicast(message, app=app)

        try:
            # Prepare data to store in the database
            batch_response_data = {
                'success_count': response.success_count,
                'failure_count': response.failure_count,
                'responses': []
            }

            for idx, resp in enumerate(response.responses):
                response_data = {
                    'token': tokens[idx],
                    'message_id': resp.message_id,
                    'exception': str(resp.exception) if resp.exception else None
                }
                batch_response_data['responses'].append(response_data)

            # Convert to JSON or another suitable format for your database
            batch_response_json = json.dumps(batch_response_data)

            PushNotificationLog.objects.create(message_title=title, message_body=description,
                                               push_notification_response=batch_response_json, project_id=project,
                                               registration_ids=tokens)
        except Exception as e:
            print("F push notification log failed", str(e))
        return Response({"status": "success", "msg": "Messages has been sent"}, status.HTTP_200_OK)
    return Response({"status": "failure", "msg": "No Members found"}, status.HTTP_400_BAD_REQUEST)


def get_s3_file_json(file_name):
    if file_name:
        s3_client = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        # Delete the file from S3
        obj = s3_client.get_object(Bucket=bucket_name, Key=file_name)
        key_file_content = obj['Body'].read()
        key_file_dict = json.loads(key_file_content)
        return key_file_dict
    return dict()


def send_user_email(subject, html_message, recipients, smtp_host=None, smtp_port=None, smtp_user=None,
                    smtp_password=None, from_email=None, from_name=None):
    # if smtp_host and smtp_port and smtp_user and smtp_password:
    #     try:
    #         # Connect to the SMTP server
    #
    #                 # delete_file_in_directory(pdf_file_name)
    #     except smtplib.SMTPException as e:
    #         # Handle SMTPException, log the details, or print an error message
    #         print(f"Error sending email: {e}")
    #         return False
    # else:
    try:
        print("smtp host", smtp_host)
        print("smtp port", smtp_port)
        print("smtp user", smtp_user)
        print("smtp smtp_password", smtp_password)
        # if smtp_host and smtp_port and smtp_user and smtp_password:
        #     # connection = get_connection(
        #     #     host=smtp_host,
        #     #     port=smtp_port,
        #     #     username=smtp_user,
        #     #     password=smtp_password,
        #     #     use_tls=True
        #     # )
        # else:
        #     connection = get_connection()

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
                print("To email:", to_email)
                if smtp_user and smtp_password and smtp_host and smtp_port:
                    with smtplib.SMTP(smtp_host, smtp_port) as server:
                        mime = MIMEMultipart()
                        server.starttls()
                        server.login(smtp_user, smtp_password)
                        mime['subject'] = subject
                        mime['to'] = str(to_email)
                        mime['from'] = str(smtp_user) if not from_name else from_name
                        mime.attach(MIMEText(msg, 'html'))
                        # Send the email
                        print("mime as string", mime.as_string())
                        server.sendmail(from_email, to_email, msg=mime.as_string())
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
                        subject=subject,
                        html_message=msg,
                        from_email=from_email if from_email else settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[to_email],
                        fail_silently=False,
                        message=msg
                    )
        return
    except Exception as e:
        print(f"Error sending email: {e}")
        return


@api_view(['POST'])
def send_mail_all_users(request):
    if request.method == 'POST':
        project_id = request.data.get('project_id')
        html = request.data.get('template')
        smtp_host = request.data.get('smtp_host')
        smtp_port = request.data.get('smtp_port')
        smtp_user = request.data.get('smtp_user')
        smtp_password = request.data.get('smtp_password')
        from_email = request.data.get('from_email')
        subject = request.data.get('subject')
        from_name = request.data.get('from_name')

        members = MemberPlatform.objects.filter(status=MEMBER_PLATFORM_ACTIVE, hide_user=False, project_id=project_id)

        send_emails = SendEmailsByProject(subject=subject, html_message=html, recipients=members, smtp_host=smtp_host,
                                          smtp_port=smtp_port, smtp_user=smtp_user, smtp_password=smtp_password,
                                          from_email=from_email,
                                          from_name=from_name)
        send_emails.start()
        return Response({"status": "success", "msg": "Emails sending initiated"}, status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def user_inactive(request):
    member_id = get_memberplatform_id(request)
    if member_id:
        MemberPlatform.objects.filter(id=member_id).update(status=MEMBER_PLATFORM_INACTIVE)
        return Response("Member Deleted Successfully", status.HTTP_200_OK)
    return Response("There is no member information", status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_logged_platform_and_projects_other_details(request):
    email_id = request.POST.get('email_id')
    member_platform = request.POST.get('member_platform')
    platform = request.POST.get('platform')
    project = request.POST.get('project')

    context = {}
    if not email_id:
        return Response({'msg': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
    member = Member.objects.filter(email_id=email_id, status=MEMBER_ACTIVE).first()
    member_platforms = MemberPlatform.objects.filter(member_id=member,status=MEMBER_PLATFORM_ACTIVE)
    if member_platform in ["True","true"]:
        member_platform_serilizer = MemberPlatformSerializer(member_platforms, many=True).data
        context["member_platforms"] = member_platform_serilizer
    
    platform_list = member_platforms.values_list('platform_id__id',flat=True)
    if platform in ["True","true"]:
        platforms = Platform.objects.filter(id__in=platform_list,status=PLATFORM_ACTIVE)
        platforms_serilizer = PlatformSerializer(platforms, many=True).data
        context["platforms"] = platforms_serilizer

    project_list = member_platforms.values_list('project_id__id',flat=True)
    if project in ["True","true"]:
        projects = Project.objects.filter(id__in=project_list,status=PROJECT_ACTIVE)
        projects_serilizer = ProjectSerializer(projects, many=True).data
        context["projects"] = projects_serilizer

    return Response(context, status.HTTP_200_OK)

    