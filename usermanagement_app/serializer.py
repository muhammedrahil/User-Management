import os
import threading
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.response import Response
from USER_MANAGEMENT import settings
import json
from usermanagement_app.models import *
from usermanagement_app.utils import add_slash_in_url, create_avatar, default_rights, delete_file_in_directory, \
    get_member_id, get_platform_id, get_project_id, \
    is_super_platform, hosted_domain_url
from usermanagement_app.flags import *


class PushNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushNotification
        fields = ('id', 'file_name', 'audio_url', 'message_body', 'push_notification_response',)


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = '__all__'

    def to_representation(self, instance):
        single_representation = super().to_representation(instance)
        if instance.logo:
            single_representation['logo'] = f'{instance.logo.url}'
        return single_representation

    def create(self, validated_data):
        request = self.context.get('request')
        name = validated_data.get('name')
        if not name:
            raise serializers.ValidationError({"msg": 'platform name is required'}, code=400)
        if not request.FILES.get('logo'):
            logo_path = create_avatar(name, 'platform')
            validated_data['logo'] = logo_path
        domain_url = request.data.get('domain_url')
        slug = slugify(str(name).strip().lower())
        if not domain_url:
            domain_url = f'https://{slug}.com/'
            validated_data['domain_url'] = domain_url
        parent_id = request.data.get('parent_id')
        if Platform.objects.filter(slug=slug, parent_id=parent_id).exclude(status=PLATFORM_DELETED).first():
            raise serializers.ValidationError({"msg": 'platform name is already exists'}, code=400)
        # domains_mapped_ganarated = [f'https://qa{slug}.com/',f'https://pre{slug}.com/',f'https://{slug}.com/']
        domains_mapped_ganarated = [f'https://{slug}.com/']
        if hosted_domain_url(request):
            domains_mapped_ganarated.append(hosted_domain_url(request))
        domains_mapped = request.data.get('mapped_domains')
        if domains_mapped:
            try:
                domains_mapped = json.loads(domains_mapped)
            except:
                domains_mapped = []
            for domain in domains_mapped:
                domains_mapped_ganarated.append(domain)
            domains_mapped_ganarated = list(set([add_slash_in_url(domain) for domain in domains_mapped_ganarated]))
        validated_data['domains_mapped'] = domains_mapped_ganarated
        validated_data['created_by'] = get_member_id(request)
        validated_data['slug'] = slug
        platform = super().create(validated_data)
        thread = threading.Thread(target=add_right_names, args=(request, platform))
        thread.start()
        return platform

    def update(self, instance, validated_data):
        name = validated_data.get('name')
        request = self.context.get('request')
        parent_id = request.data.get('parent_id')
        domain_url = request.data.get('domain_url')
        if name:
            slug = slugify(str(name).strip().lower())
            if instance.slug != slug:
                if Platform.objects.filter(slug=slug, parent_id=parent_id).exclude(id=instance.id).first():
                    raise serializers.ValidationError({"msg": 'name is already exists'}, code=400)
                if not domain_url:
                    domain_url = f'https://{slug}.com/'
                    validated_data['domain_url'] = domain_url
                    validated_data['slug'] = slug
                logo = request.FILES.get('logo')
                if not logo:
                    instence_logo_path = str(instance.logo.url).replace('/media', 'media')
                    delete_file_in_directory(instence_logo_path)
                    logo_path = create_avatar(name, 'platform')
                    validated_data['logo'] = logo_path
        # domains_mapped_ganarated = [f'https://qa{slug}.com/',f'https://pre{slug}.com/',f'https://{slug}.com/']
        domains_mapped_ganarated = [f'https://{slug}.com/']
        domains_mapped = request.data.get('mapped_domains')
        if domains_mapped:
            try:
                domains_mapped = json.loads(domains_mapped)
            except:
                domains_mapped = []
            for domain in domains_mapped:
                domains_mapped_ganarated.append(domain)
            domains_mapped_ganarated = list(set([add_slash_in_url(domain) for domain in domains_mapped_ganarated]))
        validated_data['domains_mapped'] = domains_mapped_ganarated
        validated_data['updated_by'] = get_member_id(request)
        platform_obj = super().update(instance, validated_data)
        if domain_url:
            thread = threading.Thread(target=when_changed_domain_urls_changed_users_domain_urls,
                                      args=(domain_url, platform_obj))
            thread.start()
        return platform_obj


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'

    def to_representation(self, instance):
        single_representation = super().to_representation(instance)
        if instance.logo:
            single_representation['logo'] = f'{instance.logo.url}'
        return single_representation

    def create(self, validated_data):
        request = self.context.get('request')
        platform_id = request.data.get('platform_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=400)
        name = validated_data.get('name')
        if not name:
            raise serializers.ValidationError({"msg": 'name is required'}, code=400)
        try:
            platform = Platform.objects.get(id=platform_id)
        except:
            raise serializers.ValidationError({"msg": "Platform Does not Exist"}, code=400)
        if not request.FILES.get('logo'):
            logo_path = create_avatar(name, 'project')
            validated_data['logo'] = logo_path
        parent_id = request.data.get('parent_id')
        project_name = Project.objects.filter(platform_id=platform, parent_id=parent_id, name__iexact=name).exclude(
            status=PROJECT_DELETED).first()
        project_name_for_error = ""
        if project_name:
            project_name_for_error = project_name.name
        if project_name:
            if parent_id:
                if project_name.parent_id:
                    project_name_for_error = project_name.parent_id.name
            raise serializers.ValidationError(
                {"msg": f'Company already exist, please use the associated account to access'},
                code=400)
        domain_name = request.data.get('domain_url')
        if not domain_name:
            domain_name = slugify(str(name).strip().lower())
            domain_url = f'https://{domain_name}.{platform.slug}.com/'
            if len(domain_url) < 200:
                validated_data['domain_url'] = f'https://{domain_name}.{platform.slug}.com/'
        # domains_mapped_ganarated = [f'https://qa{domain_name}.com/',f'https://pre{domain_name}.com/',f'https://{domain_name}.com/']
        domains_mapped_ganarated = list()
        if len(f'https://{domain_name}.com/') < 200:
            domains_mapped_ganarated = [f'https://{domain_name}.com/']
            if validated_data['domain_url']:
                domains_mapped_ganarated.append(validated_data['domain_url'])

        domains_mapped = request.data.get('mapped_domains')
        if domains_mapped:
            try:
                domains_mapped = json.loads(domains_mapped)
            except:
                domains_mapped = []
            for domain in domains_mapped:
                domains_mapped_ganarated.append(domain)
            domains_mapped_ganarated = list(set([add_slash_in_url(domain) for domain in domains_mapped_ganarated]))
        validated_data['domains_mapped'] = domains_mapped_ganarated
        validated_data['created_by'] = get_member_id(request)
        validated_data['platform_id'] = platform
        project = super().create(validated_data)
        thread = threading.Thread(target=add_right_names, args=(request, platform, project))
        thread.start()
        return project

    def update(self, instance, validated_data):
        request = self.context.get('request')
        platform_id = request.data.get('platform_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'The user token is not mapped as a platform id'}, code=400)
        try:
            platform = Platform.objects.get(id=platform_id)
        except:
            raise serializers.ValidationError({"msg": "Platform Does not Exist"}, code=400)
        name = validated_data.get('name')
        parent_id = request.data.get('parent_id')
        if instance.name != name:
            name = str(name).strip()
            project_name = Project.objects.filter(platform_id=platform, parent_id=parent_id, name__iexact=name).exclude(
                id=instance.id).first()
            if project_name:
                project_name_for_error = project_name.name
                if parent_id:
                    if project_name.parent_id:
                        project_name_for_error = project_name.parent_id.name
                raise serializers.ValidationError(
                    {
                        "msg": f'Company already exist, please use the associated account to access'},
                    code=400)
            logo = request.FILES.get('logo')
            if not logo and not instance.logo:
                # instence_logo_path = str(instance.logo.url).replace('/media', 'media')
                # delete_file_in_directory(instence_logo_path)
                logo_path = create_avatar(name, 'project')
                validated_data['logo'] = logo_path
        domain_url = request.data.get('domain_url')
        if not domain_url:
            domain_name = slugify(str(name).strip().lower())
            domain_url = f'https://{domain_name}.{platform.slug}.com/'
            validated_data['domain_url'] = domain_url
        # domains_mapped_ganarated = [f'https://qa{domain_name}.com/',f'https://pre{domain_name}.com/',f'https://{domain_name}.com/']
        domains_mapped_ganarated = [f'https://{domain_name}.com/']
        domains_mapped_ganarated.append(validated_data['domain_url'])
        domains_mapped = request.data.get('mapped_domains')
        if domains_mapped:
            try:
                domains_mapped = json.loads(domains_mapped)
            except:
                domains_mapped = []
            for domain in domains_mapped:
                domains_mapped_ganarated.append(domain)
            domains_mapped_ganarated = list(set([add_slash_in_url(domain) for domain in domains_mapped_ganarated]))
        validated_data['domains_mapped'] = domains_mapped_ganarated
        validated_data['updated_by'] = get_member_id(request)
        print('validated data', validated_data)
        project_obj = super().update(instance, validated_data)
        thread = threading.Thread(target=when_changed_domain_urls_changed_users_domain_urls,
                                  args=(domain_url, platform, project_obj, False))
        thread.start()
        return project_obj


def add_right_names(request, platform_id, project_id=None):
    rights_id_list = []
    rights_list = default_rights()
    for right in rights_list:
        rights_name_id = RightName.objects.create(platform_id=platform_id, project_id=project_id, name=right,
                                                  default_right_name=True)
        rights = [f'{right} Create', f'{right} Edit', f'{right} Delete']
        for name in rights:
            obj = Rights.objects.create(
                rightname_id=rights_name_id,
                name=name,
                platform_id=platform_id,
                project_id=project_id,
                default_right=True,
                created_by=get_member_id(request)
            )
            rights_id_list.append(obj.id)
    return rights_id_list


def when_changed_domain_urls_changed_users_domain_urls(domain_url, platform_id=None, project_id=None, is_platform=True):
    if is_platform:
        memberplatforms = MemberPlatform.objects.filter(platform_id=platform_id, project_id=None)
    else:
        memberplatforms = MemberPlatform.objects.filter(project_id=project_id)
    memberplatforms.update(domain_url=domain_url)
    return "domain_url Successfully Updated"


class RightNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = RightName
        fields = '__all__'

    def create(self, validated_data):
        request = self.context.get('request')
        platform_id = request.data.get('platform_id')
        project_id = request.data.get('project_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=401)
        member_id = get_member_id(request)
        validated_data['created_by'] = member_id
        validated_data['platform_id_id'] = platform_id
        if project_id:
            validated_data['project_id_id'] = project_id
        name = validated_data.get('name')
        if not name:
            raise serializers.ValidationError({"msg": 'name is required'}, code=400)
        name = str(name).strip()
        right_name = RightName.objects.filter(platform_id=platform_id, project_id=project_id,
                                              name__iexact=name).exclude(status=RIGHT_DELETED).first()
        if right_name:
            raise serializers.ValidationError({"msg": 'right name is already exists'}, code=400)
        validated_data['name'] = name
        single_create = super().create(validated_data)
        name = single_create.name
        platform_id = single_create.platform_id
        project_id = single_create.project_id
        rights = [f'{name} Create', f'{name} Edit', f'{name} Delete']
        for rights in rights:
            Rights.objects.create(
                rightname_id=single_create,
                name=rights,
                platform_id=platform_id,
                project_id=project_id,
                created_by=member_id
            )
        return single_create

    def to_representation(self, instance):
        single_representation = super().to_representation(instance)
        rights = instance.rights_rightname.all()
        rights = RightsSerializer(rights, many=True).data
        single_representation['rights'] = rights
        return single_representation

    def update(self, instance, validated_data):
        request = self.context.get('request')
        member_id = get_member_id(request)
        platform_id = request.data.get('platform_id')
        project_id = request.data.get('project_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=401)
        validated_data['platform_id_id'] = platform_id
        if project_id:
            validated_data['project_id_id'] = project_id
        validated_data['updated_by'] = member_id
        name = validated_data.get('name')
        if name:
            name = str(name).strip()
            if instance.name != name:
                if RightName.objects.filter(platform_id=platform_id, project_id=project_id, name__iexact=name).exclude(
                        status=RIGHT_DELETED).first():
                    raise serializers.ValidationError({"msg": 'right name is already exists'}, code=400)
                validated_data['name'] = name
        single_update = super().update(instance, validated_data)
        rights = single_update.rights_rightname.all()
        for right in rights:
            name = right.name
            if 'Create' in name:
                name = f'{single_update.name} Create'
            if 'Edit' in name:
                name = f'{single_update.name} Edit'
            if 'Delete' in name:
                name = f'{single_update.name} Delete'
            right.name = name
            right.updated_by = member_id
            right.save()
        return single_update


class RightsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rights
        fields = '__all__'


class UserTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserType
        fields = '__all__'

    def to_representation(self, instance):
        single_representation = super().to_representation(instance)
        platform_id = instance.platform_id
        project_id = instance.project_id
        if not project_id:
            member_usertype_count = MemberPlatform.objects.filter(usertype_id=instance,
                                                                  platform_id=platform_id,
                                                                  status=MEMBER_PLATFORM_ACTIVE)
        else:
            member_usertype_count = MemberPlatform.objects.filter(usertype_id=instance,
                                                                  platform_id=platform_id, project_id=project_id,
                                                                  status=MEMBER_PLATFORM_ACTIVE)
        single_representation['user_type_count'] = member_usertype_count.count()
        return single_representation

    def create(self, validated_data):
        request = self.context.get('request')
        member_id = get_member_id(request)
        project_id = request.data.get('project_id')
        platform_id = request.data.get('platform_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=401)
        name = validated_data.get('name')

        if not name:
            raise serializers.ValidationError({"msg": 'name is required'}, code=400)
        name = str(name).strip()
        if UserType.objects.filter(platform_id=platform_id, project_id=project_id, name__iexact=name).exclude(
                status=USERTYPE_DELETED).first():
            print('Usertype already excists')
            raise serializers.ValidationError({"msg": 'UserType name is already exists'}, code=401)
        validated_data['created_by'] = member_id
        validated_data['platform_id_id'] = platform_id
        validated_data['project_id_id'] = project_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        member_id = get_member_id(request)
        project_id = request.data.get('project_id')
        platform_id = request.data.get('platform_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=401)
        name = validated_data.get('name')
        if name:
            name = str(name).strip()
            if instance.name != name:
                if UserType.objects.filter(platform_id=platform_id, project_id=project_id, name__iexact=name).exclude(
                        status=USERTYPE_DELETED).first():
                    raise serializers.ValidationError({"msg": 'UserType name is already exists'}, code=400)
                validated_data['name'] = name
        validated_data['platform_id_id'] = platform_id
        if platform_id:
            validated_data['project_id_id'] = project_id
        validated_data['updated_by'] = member_id
        return super().update(instance, validated_data)


class RolesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Roles
        fields = '__all__'

    def to_representation(self, instance):
        single_representation = super().to_representation(instance)
        platform_id = instance.platform_id
        project_id = instance.project_id
        rights_ids = instance.rights_ids.all()
        rights = RightsSerializer(rights_ids, many=True).data
        if not project_id:
            role_member_count = MemberPlatform.objects.filter(roles_id=instance,
                                                              platform_id=platform_id, status=MEMBER_PLATFORM_ACTIVE)
        else:
            role_member_count = MemberPlatform.objects.filter(roles_id=instance,
                                                              platform_id=platform_id, project_id=project_id,
                                                              status=MEMBER_PLATFORM_ACTIVE)

        single_representation['users_count'] = role_member_count.count() or 0
        single_representation['rights_ids'] = rights
        return single_representation

    def create(self, validated_data):
        request = self.context.get('request')
        platform_id = request.data.get('platform_id')
        project_id = request.data.get('project_id')
        usertype_id = request.data.get('usertype_id')
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        if not platform_id:
            raise serializers.ValidationError({"msg": 'Please provide platform id'}, code=400)
        if not usertype_id:
            raise serializers.ValidationError({"msg": 'Please provide usertype id'}, code=400)
        name = validated_data.get('name')
        if not name:
            raise serializers.ValidationError({"msg": 'name is required'}, code=400)
        name = str(name).strip()
        if Roles.objects.filter(platform_id=platform_id, project_id=project_id, name__iexact=name).exclude(
                status=ROLE_DELETED).first():
            raise serializers.ValidationError({"msg": 'Role name is already exists'}, code=400)
        member_id = get_member_id(request)
        validated_data['created_by'] = member_id
        validated_data['platform_id_id'] = platform_id
        validated_data['project_id_id'] = project_id
        return super().create(validated_data)

    def update(self, instance, validated_data):
        request = self.context.get('request')
        platform_id = request.data.get('platform_id')
        project_id = request.data.get('project_id')
        name = validated_data.get('name')
        if name:
            name = str(name).strip()
            if instance.name != name:
                if Roles.objects.filter(platform_id=platform_id, project_id=project_id, name__iexact=name).exclude(
                        status=ROLE_DELETED).first():
                    raise serializers.ValidationError({"msg": 'Role name is already exists'}, code=400)
                validated_data['name'] = name
        if not is_super_platform(request):
            platform_id = get_platform_id(request)
            if get_project_id(request):
                project_id = get_project_id(request)
        member_id = get_member_id(request)
        validated_data['updated_by'] = member_id
        validated_data['platform_id_id'] = platform_id
        validated_data['project_id_id'] = project_id
        return super().update(instance, validated_data)


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = '__all__'


class MemberPlatformLoginListViewSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberPlatform
        fields = '__all__'

    def to_representation(self, instance):
        new_representation = {}
        name = instance.platform_id.name
        logo = instance.platform_id.logo if instance.platform_id.logo else None
        if logo:
            logo = f'{logo.url}'
        if instance.project_id:
            name = instance.project_id.name
        new_representation['name'] = name
        new_representation['id'] = instance.id
        new_representation['logo'] = logo
        return new_representation


class MemberPlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = MemberPlatform
        fields = '__all__'

    def to_representation(self, instance):
        new_representation = {
            "member_id": str(instance.member_id.id),
            "memberplatform_id": str(instance.id),
            "memberplatform_status": instance.status,
        }
        new_representation["platform_deatails"] = {
            "platform_id": str(instance.platform_id.id),
            "platform_name": instance.platform_id.name,
            "platform_code": instance.platform_id.code,
            "platform_website": instance.platform_id.website,
            "is_super_platform": instance.platform_id.is_super_platform
        }
        new_representation["memberinformation_deatails"] = {
            "memberinformation_id": str(instance.memberinformation_id.id),
            "first_name": instance.memberinformation_id.first_name,
            "last_name": instance.memberinformation_id.last_name,
            "email_id": instance.memberinformation_id.email_id,
            "phone_number": instance.memberinformation_id.phone_number,
            "country_code": instance.memberinformation_id.country_code,
            "address_line_1": instance.memberinformation_id.address_line_1,
            "address_line_2": instance.memberinformation_id.address_line_2,
            "country": instance.memberinformation_id.country,
            "state": instance.memberinformation_id.state,
            "city": instance.memberinformation_id.city,
            "zip_code": instance.memberinformation_id.zip_code,
            "profile_image": f"{instance.memberinformation_id.profile_image.url}" if instance.memberinformation_id.profile_image else None,
        }
        new_representation["usertype_deatails"] = {
            "usertype_id": instance.usertype_id.id if instance.usertype_id else None,
            "usertype_name": instance.usertype_id.name if instance.usertype_id else None,
        }
        new_representation["role_deatails"] = {
            "role_id": instance.roles_id.id if instance.roles_id else None,
            "role_name": instance.roles_id.name if instance.roles_id else None,
        }
        new_representation["project_deatails"] = {
            "project_id": str(instance.project_id.id) if instance.project_id else None,
            "project_name": str(instance.project_id.name) if instance.project_id else None,
            "project_code": str(instance.project_id.code) if instance.project_id else None,
            "project_website": str(instance.project_id.website) if instance.project_id else None,
        }
        return new_representation


class MappedURlsSerializer(serializers.ModelSerializer):
    class Meta:
        model = MappedURls
        fields = '__all__'


class FcmKeysSerializer(serializers.ModelSerializer):
    class Meta:
        model = FcmKeys
        fields = '__all__'
