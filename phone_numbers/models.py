from django.db import models
from django.utils import timezone
import os
from django.conf import settings

STATUS_CHOICES = [
    ('pending', 'Ожидает'),
    ('in_progress', 'В процессе'),
    ('completed', 'Готово'),
    ('failed', 'Ошибка'),
]

STATUS_TOOLTIPS = {
    'pending': 'Номер находится в очереди на обработку',
    'in_progress': 'Идет обработка номера (звонок или генерация summary)',
    'completed': 'Есть summary и номер не находится в очереди',
    'failed': 'Возникли ошибки в процессе обработки',
}

class PhoneNumber(models.Model):
    number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_called_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, null=True)
    summary_updated_at = models.DateTimeField(null=True, blank=True)
    processing_time = models.DurationField(null=True, blank=True)

    def __str__(self):
        return self.number
    
    def recall(self, reset_counter=False):
        """
        Метод для повторного набора номера
        При ручном вызове удаляет последнюю неудачную запись
        """
        if reset_counter:
            # Сначала пробуем найти и удалить последнюю запись без транскрипции
            last_empty_record = self.call_records.filter(
                models.Q(transcript__isnull=True) | models.Q(transcript='')
            ).order_by('-created_at').first()
            
            if last_empty_record:
                last_empty_record.delete()
            else:
                # Если нет записей без транскрипции, удаляем самую последнюю
                last_record = self.call_records.order_by('-created_at').first()
                if last_record:
                    last_record.delete()
        
        self.add_to_queue()
        return True
        
    def check_transcription_status(self):
        """
        Проверяет все записи звонков и обновляет статус,
        если все транскрипции неудачные
        """
        records = self.call_records.all()
        if not records.exists():
            return
            
        all_failed = all(
            record.transcript == "Audio could not be transcribed"
            for record in records
            if record.transcript  # проверяем только записи с транскрипцией
        )
        
        # Проверяем, что все записи имеют транскрипцию
        all_transcribed = all(record.transcript for record in records)
        
        if all_failed and all_transcribed:
            self.status = 'failed'
            self.save(update_fields=['status'])

    def add_to_queue(self):
        """Добавляет номер в очередь звонков"""
        from .models import CallQueue
        CallQueue.objects.create(phone_number=self)
        # Используем флаг для предотвращения рекурсии при сохранении
        self._skip_status_update = True
        self.status = 'pending'
        self.save()
        delattr(self, '_skip_status_update')
        
    def save(self, *args, **kwargs):
        is_new = self.pk is None  # Проверяем, новый ли это объект
        
        # Если есть summary и нет активной очереди, статус должен быть "Готово"
        if self.summary and not hasattr(self, '_skip_status_update'):
            from .models import CallQueue
            if not CallQueue.objects.filter(phone_number=self).exists():
                self.status = 'completed'
        
        super().save(*args, **kwargs)
        
        # Если это новый объект, создаем первую запись в call_records
        if is_new:
            from .models import CallRecord
            CallRecord.objects.create(phone_number=self)

    def get_processing_time(self):
        """Вычисляет время обработки как разницу между созданием номера и первым summary"""
        if self.summary and self.summary_updated_at:
            processing_time = self.summary_updated_at - self.created_at
            return processing_time
        return None

    def format_processing_time(self):
        """Форматирует время обработки в читаемый вид"""
        processing_time = self.get_processing_time()
        if processing_time:
            total_seconds = int(processing_time.total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            
            if hours > 0:
                return f"{hours}ч {minutes}м {seconds}с"
            elif minutes > 0:
                return f"{minutes}м {seconds}с"
            else:
                return f"{seconds}с"
        return "Не обработан"

    def get_status_tooltip(self):
        """Возвращает текст подсказки для текущего статуса"""
        return STATUS_TOOLTIPS.get(self.status, '')
    
    @property
    def call_attempts(self):
        """
        Возвращает реальное количество попыток звонка на основе записей
        """
        return self.call_records.count()


class CallRecord(models.Model):
    phone_number = models.ForeignKey(PhoneNumber, on_delete=models.CASCADE, related_name='call_records')
    created_at = models.DateTimeField(auto_now_add=True)
    audio_file = models.FileField(upload_to='recordings/', null=True, blank=True)
    transcript = models.TextField(blank=True)
    
    def get_audio_file_path(self):
        """
        Возвращает полный путь к аудиофайлу
        """
        if self.audio_file:
            # Используем BASE_DIR и полный путь к файлу
            file_path = os.path.join(settings.BASE_DIR, str(self.audio_file))
            # Проверяем существование файла
            if os.path.exists(file_path):
                return file_path
            else:
                print(f"Файл не найден: {file_path}")
        return None

    def __str__(self):
        return f"{self.phone_number} - {self.created_at}"

class CallQueue(models.Model):
    phone_number = models.ForeignKey(PhoneNumber, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    priority = models.IntegerField(default=0)  # Для возможного будущего приоритетного обзвона
    
    class Meta:
        ordering = ['created_at']  # Сортировка по времени создания
        
    def __str__(self):
        return f"Call queue item for {self.phone_number.number} created at {self.created_at}"

class Settings(models.Model):
    key = models.CharField(max_length=50, unique=True)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Settings"
    
    def __str__(self):
        return self.key

    @classmethod
    def get_value(cls, key, default=None):
        try:
            return cls.objects.get(key=key).value
        except cls.DoesNotExist:
            return default
