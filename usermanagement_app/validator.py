import os
from django.core.exceptions import ValidationError



def validate_profile_image_extension(value):
    ext = os.path.splitext(value.name)[1]  # [0] returns path+filename
    valid_extensions = ['.png', '.jpg', '.jpeg']
    if ext.lower() not in valid_extensions:
        raise ValidationError(
            'Unsupported file extension. Only PNG, JPG, JPEG, file allowed')