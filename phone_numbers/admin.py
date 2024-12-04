from django.contrib import admin
from django.utils.html import format_html
from .models import PhoneNumber, CallRecord, Settings, CallQueue

@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ('number', 'created_at', 'last_called_at', 'summary_updated_at', 'processing_time')
    search_fields = ('number',)
    readonly_fields = ('created_at', 'last_called_at', 'summary_updated_at', 'processing_time')

@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'created_at', 'audio_file_link')
    search_fields = ('phone_number__number',)
    readonly_fields = ('created_at', 'audio_file_display')

    def audio_file_link(self, obj):
        if obj.audio_file:
            return format_html('<a href="/{}" target="_blank">Прослушать</a>', obj.get_audio_file_path())
        return 'Нет файла'
    audio_file_link.short_description = 'Аудиофайл'

    def audio_file_display(self, obj):
        if obj.audio_file:
            return format_html('<audio controls><source src="/{}" type="audio/wav"></audio>', obj.get_audio_file_path())
        return 'Нет файла'
    audio_file_display.short_description = 'Предпросмотр аудио'

@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'description')
    search_fields = ('key',)

@admin.register(CallQueue)
class CallQueueAdmin(admin.ModelAdmin):
    list_display = ('phone_number', 'created_at', 'priority')
    list_filter = ('priority',)
    search_fields = ('phone_number__number',)
    ordering = ['created_at']
