
INACTIVE = 0
ACTIVE = 1
DELETED = 2

# status for Platform
PLATFORM_INACTIVE = 0
PLATFORM_ACTIVE = 1
PLATFORM_DELETED = 2

# status for Organization
PROJECT_INACTIVE = 0
PROJECT_ACTIVE = 1
PROJECT_DELETED = 2

MEMBER_PLATFORM_INACTIVE = 0
MEMBER_PLATFORM_ACTIVE = 1
MEMBER_PLATFORM_DELETE = 2

MEMBER_INACTIVE = 0
MEMBER_ACTIVE = 1
MEMBER_DELETED = 2

RIGHT_INACTIVE = 0
RIGHT_ACTIVE = 1
RIGHT_DELETED = 2

ROLE_INACTIVE = 0
ROLE_ACTIVE = 1
ROLE_DELETED = 2

USERTYPE_INACTIVE = 0
USERTYPE_ACTIVE = 1
USERTYPE_DELETED = 2

# forgot password link validation
PASSWORD_SET = 1
PASSWORD_NOT_SET = 0

MEMBER_INFORMATION_INACTIVE = 0
MEMBER_INFORMATION_ACTIVE = 1
MEMBER_INFORMATION_DELETED = 2

MEMBER_PLATFORM_STATUSES = (
    (MEMBER_PLATFORM_ACTIVE, "Active"),
    (MEMBER_PLATFORM_INACTIVE, "Inactive"),
    (MEMBER_PLATFORM_DELETE, "Deleted"),
)

NOTIFICAION_INACTIVE = 0
NOTIFICAION_ACTIVE = 1
NOTIFICAION_DELETED = 2

VERIFICATION_INACTIVE = 0
VERIFICATION_ACTIVE = 1
VERIFICATION_DELETED = 2

NOTIFICATION_DELETED = 0  # notification deleted1
NOTIFICATION_REQUEST_RECEIVED = 1  # notification request received from initiator
NOTIFICATION_INITIATED = 2  # notification sent to service provider from notification engine
NOTIFICATION_DELIVERED_SUCCESS = 3  # notification delivered to user successfully
NOTIFICATION_DELIVERED_FAILED = 4  # notification not delivered to user