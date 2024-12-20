from django.apps import AppConfig

class PhoneNumbersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'phone_numbers'
    
    def ready(self):
        import phone_numbers.signals  # noqa
