from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PhoneNumber, Settings

@receiver(post_save, sender=PhoneNumber)
def phone_number_post_save(sender, instance, created, **kwargs):
    if created:
        # Ensure default settings exist
        default_settings = {
            'recall_interval_hours': ('24', 'Hours between automatic recall attempts'),
            'max_retries': ('3', 'Maximum number of retry attempts for failed calls'),
            'transcription_model': ('base', 'Whisper model to use for transcription')
        }
        
        for key, (value, description) in default_settings.items():
            Settings.objects.get_or_create(
                key=key,
                defaults={'value': value, 'description': description}
            )
