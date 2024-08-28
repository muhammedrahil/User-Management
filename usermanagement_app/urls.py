from rest_framework import routers
from django.urls import path, include

from usermanagement_app.views import *

router = routers.DefaultRouter()
router.register('platform', PlatformViewSet, basename='platform_viewset')
router.register('project', ProjectViewSet, basename='project_viewset')
router.register('right', RightNameViewSet, basename='rights_viewset')
router.register('usertype', UserTypeViewSet, basename='usertype_viewset')
router.register('role', RolesViewSet, basename='roles_viewset')
router.register('mappedurls', MappedURlsViewSet, basename='mappedurls_viewset')
router.register('push_notification_history', PushNotificationHistoryViewSet, basename='pushnotificationhistory_viewset')
router.register('fcm_keys', FcmKeysViewSet, basename='fcmkeys_viewset')

urlpatterns = [
    path('', include(router.urls)),
    path('super_platform/create/seeder/', super_platform_create_seeder),
    path('member/registration/', member_registration_without_token),
    path('login/token/<uuid:member_platform_id>/', LoginTokenView.as_view(), name='login-token'),
    path('login/password/domain_url/', LoginPasswordDomaiUrlAndGoogleAPIView.as_view(),
         name='login-password-domain_url-google-login'),  # login with password
    path('login/password/<uuid:member_platform_id>/', LoginPasswordMemberPlatformAPIView.as_view(),
         name='login-password-memberplatform'),
    path('logout/<uuid:member_platform_id>/', LogoutMemberPlatformAPIView.as_view()),

    path('member_platform_forget_password_send_to_link/<uuid:member_platform_id>/',
         member_platform_forget_password_send_to_link),
    path('member_platform_password_verification/', member_platform_password_verification),
    path('otp/verify/', verify_otp),
    path('otp/trigger/', trigger_otp),
    path('password_verification_by_link/', password_verification_by_link),
    path('password/update/', password_update),
    path('members/list/', MemberPlatformListAPIView.as_view(), name='member-list'),  # member list
    path('members/list/perticular/', MemberPlatformListPerticularWaysAPIView.as_view(), name='member-list-perticular'),
    # member list
    path('member/create/', member_create),
    path('member/delete/<uuid:member_platform_id>/', member_delete),
    path('member/single/<uuid:member_platform_id>/', member_single),
    path('member/update/<uuid:member_platform_id>/', member_update),
    path('member/status/update/<uuid:member_platform_id>/', member_status_update),
    path('platforms/dropdown/', platforms_dropdown),
    path('projects/dropdown/', projects_dropdown),
    path('usertypes/dropdown/', user_types_dropdown),
    path('rights/dropdown/', rights_dropdown),
    path('roles/dropdown/', roles_dropdown),
    path('members/dropdown/', members_platform_dropdown),
    # path('delete/all/', delete_all),
    path('platform_id/domain_mapped_url', get_id_by_respective_data),
    path('member/sign_up/', member_sign_up),
    path('member/list/without/search', member_list_without_search),
    path('projects_list/', projects_listed_based_on_gn_platform),
    path('custom_right_create/', custom_right_create),
    path('member_details/hard_delete/', member_details_hard_delete),
    path('sub_projects_list/', ProjectWaysUsersDropDownList.as_view({"post": "project_list"}),
         name='sub_projects_list'),
    path('project_users_list/', ProjectWaysUsersDropDownList.as_view({'post': 'get_users_detail_params'}),
         name='project_userslist'),
    path('login/password/app/', MobileLogin.as_view({'post': 'login'}), name='login'),
    path('check/old/password/', check_old_password),
    path('forget_password/platform/ways/', ForgetPasswordforPlatformWays.as_view({'post': 'get_email'}),
         name='forget_password_platform_ways'),
    path('projects/member_id/', projects_based_member_ids),
    path('mem_details/mem_platform_id/', member_details_by_mem_platform_id),
    path('get_parent_projects_list/', ListOfProjectsListBasedonProject.as_view({"post": "get_projectsList"}),
         name='get_parent_projects_list'),
    path('get_project_based_user_token/',
         ListOfProjectsListBasedonProject.as_view({"post": "get_project_based_user_token"}),
         name='get_project_based_user_token'),
    path('member_info_check/', memberinfo_check),
    path('overall/member/list', overall_members_lists),
    path('apple/sign_in/', AppleSignIn.as_view()),
    path('role_check/', is_role_mapped),
    path('push/notification/', PushNotificationView.as_view()),
    path('push/notification/count/', get_pushnotification_count),
    path('send/email/', SendEmail.as_view()),
    path('users/', Users.as_view(), name="Users List"),
    path('create/user/', CreateUsers.as_view(), name="Create User"),
    path('assign/user/<uuid:member_platform_id>/<uuid:target_project_id>/', assign_user),
    path('members/dropdown/paginated/', members_platform_dropdown_pagination),
    path('roles/list/dropdown/', roles_list_dropdown),
    path('admin/account/', get_admin_account),
    path('push_notification/all_users/<uuid:project_id>/', send_push_notification_for_all_users),
    path('send_mail_users/', send_mail_all_users),
    path('user_delete/', user_inactive),
    path('get_logged_platform_and_projects_other_details/', get_logged_platform_and_projects_other_details),
]
