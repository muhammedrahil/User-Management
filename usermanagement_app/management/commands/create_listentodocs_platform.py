from rest_framework import request

from usermanagement_app.models import MappedURls, Platform, Member, MemberPlatform, MemberInformation, Roles, UserType, \
    Rights, RightName
from django.core.management.base import BaseCommand
from usermanagement_app.flags import PLATFORM_ACTIVE, MEMBER_PLATFORM_ACTIVE

from usermanagement_app.utils import default_rights, password_hash


def add_right_names( platform_id, project_id=None):
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
                default_right=True,
            )
            rights_id_list.append(obj)
    return rights_id_list



class Command(BaseCommand):
    help = 'Create Super Platform'

    def handle(self, *args, **options):
        Platform_data = {"code": "LISTENTODOC",
                         "slug": "listen-to-doc",
                         "name": "Listen to Doc",
                         'website': 'https://www.listentodoc.com',
                         "domain_url": 'https://devlistendoc.zaiportal.com/',
                         "status": PLATFORM_ACTIVE,
                         "is_super_platform": True,
                         "domains_mapped": [
                            "https://devlistendoc.zaiportal.com/"
                         ]
                         }
        platform = Platform.objects.filter(slug=Platform_data.get('slug')).first()
        if not platform:
            platform = Platform.objects.create(**Platform_data)
        domains_mapped_urls = platform.domains_mapped or []
        for domains_mapped_url in domains_mapped_urls:
            MappedURls.objects.create(
                platform_id=platform,
                domain_url=domains_mapped_url,
            )
        user_type = UserType.objects.create(
            name="Administrator",
            platform_id=platform,
        )
        role = Roles.objects.create(
            name="Admin",
            platform_id=platform,
            usertype_id=user_type,
        )
        role_rights = add_right_names(platform)
        for right in role_rights:
            try:
                role.rights_ids.add(right)
            except:
                pass
        """Super Admin create"""
        # For Create Test user as super Admin
        member = Member.objects.filter(email_id='bala@zaigoinfotech.com').first()
        if not member:
            member = Member.objects.create(email_id='bala@zaigoinfotech.com', phone_number='8667668231',
                                           is_superuser=True)
        memberinformation = MemberInformation.objects.create(first_name='Bala', last_name='Muruga',
                                                             email_id='bala@zaigoinfotech.com',
                                                             phone_number='8667668231', country_code="+91",
                                                             password=password_hash('Password@123'))
        MemberPlatform.objects.create(member_id=member,
                                      platform_id=platform,
                                      memberinformation_id=memberinformation,
                                      usertype_id=user_type,
                                      roles_id=role,
                                      status=MEMBER_PLATFORM_ACTIVE,
                                      domain_url='https://devlistendoc.zaiportal.com/')
