from rest_framework.exceptions import APIException
from rest_framework.permissions import BasePermission


class PlatformPermitted(BasePermission):
    def has_permission(self, request, view):
        if request.auth:
            rights = request.auth['rights']
            if request.method == "POST":
                if "platform Create" not in rights:
                    raise APIException({'msg': "Invalid Access Token Provided"})
            # if request.method == "PUT" or request.method == "PATCH":
            #     if "platform Edit" not in rights:
            #         return False
            # if request.method == "DELETE":
            #     if "platform Delete" not in rights:
            #         return False
            return True