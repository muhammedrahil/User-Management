from django.apps import AppConfig


class UsermanagementAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usermanagement_app'

    def ready(self):
        import usermanagement_app.signals
