# TODO REVIEW
from django.apps import AppConfig


class PayfastConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'payfast'
    initialized = False


    @classmethod
    def initialize(cls):
        if cls.initialized:
            return
        cls.initialized = True

        # Only import settings, checks, and signals one time after Django has been initialized
        from payfast.conf import settings
        from payfast import signals

        settings.configure_django()


    def ready(self):
        self.initialize()
