import os
import openai
from datetime import datetime
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from django.db import models
import speech_recognition as sr
import pjsua as pj
import time
import glob
from pathlib import Path
from dotenv import load_dotenv
from phone_tracker.celery import app  # Добавляем импорт app

# Load environment variables
load_dotenv()

# Проверяем загрузку переменных окружения
print(f"SIP_USER: {os.getenv('SIP_USER')}")
print(f"SIP_DOMAIN: {os.getenv('SIP_DOMAIN')}")
print(f"SIP_AUTH_REALM: {os.getenv('SIP_AUTH_REALM')}")
print(f"SIP_AUTH_USERNAME: {os.getenv('SIP_AUTH_USERNAME')}")

# Logging callback
def log_cb(level, msg, length):
    try:
        print(msg.decode('utf-8'))
    except UnicodeDecodeError:
        print("Logging error: Unable to decode message.")

# Call state callback
class CallCallback(pj.CallCallback):
    def __init__(self, call=None):
        super().__init__(call)
        self.recorder_id = None
        self.recording_filename = None

    def on_state(self):
        print(f"Call state: {self.call.info().state_text}")
        if self.call.info().state == pj.CallState.DISCONNECTED:
            if self.recorder_id is not None:
                try:
                    lib.recorder_destroy(self.recorder_id)
                    print(f"Recorder destroyed for: {self.recording_filename}")
                except pj.Error as e:
                    print(f"Error destroying recorder: {str(e)}")
                self.recorder_id = None

    def on_media_state(self):
        if self.call.info().media_state == pj.MediaState.ACTIVE:
            call_slot = self.call.info().conf_slot
            try:
                # Create recordings directory if it doesn't exist
                recordings_dir = os.path.join("recordings", self.call.info().remote_uri.split('@')[0].split(':')[1])
                if not os.path.exists(recordings_dir):
                    os.makedirs(recordings_dir)
                
                # Generate recording filename
                self.recording_filename = os.path.join(
                    recordings_dir,
                    f"call_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
                )
                
                # Create recorder and connect call slot to recorder slot
                self.recorder_id = lib.create_recorder(self.recording_filename)
                rec_slot = lib.recorder_get_slot(self.recorder_id)
                lib.conf_connect(call_slot, rec_slot)
                print(f"Recording started: {self.recording_filename}")
            except pj.Error as e:
                print(f"Error setting up recorder: {str(e)}")

# Account callback
class AccountCallback(pj.AccountCallback):
    def __init__(self, account=None):
        super().__init__(account)

    def on_reg_state(self):
        print(f"Registration state: {self.account.info().reg_status} ({self.account.info().reg_reason})")

# Отложенный импорт моделей
def get_phone_number_model():
    from .models import PhoneNumber
    return PhoneNumber

def get_call_record_model():
    from .models import CallRecord
    return CallRecord

def get_settings_model():
    from .models import Settings
    return Settings

def get_call_queue_model():
    from .models import CallQueue
    return CallQueue

@shared_task
def process_phone_number(phone_id):
    """Process a phone number: make call and record conversation"""
    global lib
    lib = None
    try:
        phone = get_phone_number_model().objects.get(id=phone_id)
        print(f"Processing phone number: {phone.number}")
        if phone.call_attempts >= 15:
            print(f"Skipping call to {phone.number} - maximum attempts (15) reached")
            return
        
        
        # Get SIP credentials
        sip_user = os.getenv('SIP_USER')
        sip_domain = os.getenv('SIP_DOMAIN')
        sip_realm = os.getenv('SIP_AUTH_REALM')
        sip_username = os.getenv('SIP_AUTH_USERNAME')
        sip_password = os.getenv('SIP_AUTH_PASSWORD')

        if not all([sip_user, sip_domain, sip_realm, sip_username, sip_password]):
            raise Exception("SIP credentials not found in environment variables")

        print(f"Using SIP credentials: user={sip_user}, domain={sip_domain}, realm={sip_realm}")
        
        # Initialize PJSUA library
        lib = pj.Lib()
        
        # Configure the library with enhanced settings
        media_cfg = pj.MediaConfig()
        media_cfg.no_vad = True
        media_cfg.enable_ice = True
        media_cfg.clock_rate = 16000
        
        # Configure NAT and UA settings
        ua_cfg = pj.UAConfig()
        ua_cfg.force_lr = True
        ua_cfg.user_agent = "PJSUA v2.14.1 NAT"
        ua_cfg.max_calls = 1
        ua_cfg.nameserver = ["8.8.8.8", "8.8.4.4"]

        # Initialize library with logging
        lib.init(
            ua_cfg=ua_cfg,
            log_cfg=pj.LogConfig(level=4, callback=log_cb),
            media_cfg=media_cfg
        )

        # Use NULL sound device
        lib.set_null_snd_dev()
        print("Using NULL audio device")

        # Create UDP transport with STUN and proper IP configuration
        transport_cfg = pj.TransportConfig()
        transport_cfg.public_addr = os.getenv('LOCAL_IP')
        transport = lib.create_transport(pj.TransportType.UDP, transport_cfg)
        print(f"Transport created with public address {transport_cfg.public_addr}")
        print(f"Local binding: {transport.info().host}:{transport.info().port}")

        # Start the library
        lib.start()

        # Configure SIP account with enhanced NAT settings
        acc_cfg = pj.AccountConfig()
        acc_cfg.id = f"sip:{sip_user}@{sip_domain}"
        acc_cfg.reg_uri = f"sip:{sip_domain}"
        acc_cfg.auth_cred = [pj.AuthCred(
            sip_realm,
            sip_username,
            sip_password
        )]
        
        # Enhanced NAT and media settings
        acc_cfg.allow_contact_rewrite = True
        acc_cfg.contact_rewrite_method = 2
        acc_cfg.contact_force_contact = f"sip:{sip_user}@{os.getenv('LOCAL_IP')}"
        acc_cfg.reg_timeout = 300
        acc_cfg.rtp_port = 10000
        acc_cfg.rtp_port_range = 1000

        # Create account and wait for registration
        acc = lib.create_account(acc_cfg, cb=AccountCallback())
        print("Waiting for registration...")
        time.sleep(3)

        # Make the call
        try:
            uri = f"sip:{phone.number}@nyc.us.out.didww.com"
            print(f"Dialing: {uri}")
            call = acc.make_call(uri, cb=CallCallback())
            
            # Получаем максимальную длительность звонка из настроек (по умолчанию 60 секунд)
            Settings = get_settings_model()
            max_call_duration = int(Settings.get_value('max_call_duration', '60'))
            start_time = time.time()
            
            # Ждем завершения звонка с учетом максимальной длительности
            time.sleep(2)  # Даем время на установление соединения
            while (call and call.is_valid() and 
                   call.info().state != pj.CallState.DISCONNECTED and 
                   time.time() - start_time < max_call_duration):
                time.sleep(0.5)
            
            # Если звонок все еще активен после достижения максимальной длительности
            if (call and call.is_valid() and 
                call.info().state != pj.CallState.DISCONNECTED):
                try:
                    print(f"Call exceeded maximum duration of {max_call_duration}s, hanging up: {phone.number}")
                    call.hangup()
                except pj.Error as e:
                    print(f"Error hanging up call: {str(e)}")
            else:
                print(f"Call ended normally: {phone.number}")

        except pj.Error as e:
            print(f"Error making call to {phone.number}: {str(e)}")

        # Update phone record
        phone.last_called_at = timezone.now()
        phone.save()

        # Check for new recordings
        check_recordings.delay(phone_id)

    except Exception as e:
        print(f"Error processing phone {phone_id}: {str(e)}")
    finally:
        if lib:
            try:
                print("Destroying library...")
                lib.destroy()
            except Exception as e:
                print(f"Error destroying library: {str(e)}")

@shared_task
def check_recordings(phone_id):
    """Check for new recordings and process them"""
    try:
        phone = get_phone_number_model().objects.get(id=phone_id)
        recordings_dir = os.path.join("recordings", phone.number)
        
        if os.path.exists(recordings_dir):
            # Get all wav files that haven't been processed
            processed_files = set(get_call_record_model().objects.filter(
                phone_number=phone
            ).values_list('audio_file', flat=True))
            
            all_files = set(glob.glob(os.path.join(recordings_dir, "*.wav")))
            new_files = all_files - processed_files
            
            # Initialize speech recognition
            recognizer = sr.Recognizer()
            
            for audio_file in new_files:
                # Create call record
                call_record = get_call_record_model().objects.create(
                    phone_number=phone,
                    audio_file=audio_file
                )
                
                # Transcribe audio using Google Speech Recognition
                try:
                    with sr.AudioFile(audio_file) as source:
                        audio = recognizer.record(source)
                    transcript = recognizer.recognize_google(audio)
                    
                    # Save transcript
                    call_record.transcript = transcript
                    call_record.save()
                    
                    # Generate summary
                    generate_summary.delay(phone.id)
                except sr.UnknownValueError:
                    print(f"Google Speech Recognition could not understand the audio: {audio_file}")
                    call_record.transcript = "Audio could not be transcribed"
                    call_record.save()
                except sr.RequestError as e:
                    print(f"Could not request results from Google Speech Recognition service; {str(e)}")
                    call_record.transcript = "Error during transcription"
                    call_record.save()
                
    except Exception as e:
        print(f"Error checking recordings for phone {phone_id}: {str(e)}")

@shared_task
def generate_summary(phone_id):
    try:
        phone = get_phone_number_model().objects.get(id=phone_id)
        
        # Collect all transcripts
        transcripts = get_call_record_model().objects.filter(phone_number=phone).values_list('transcript', flat=True)
        combined_text = " ".join(transcripts)
        
        # Generate summary using OpenAI
        messages = [
            {
                "role": "user",
                "content": (
                    f"{settings.SUMMARY_PROMPT}\n\nText to analyze:\n[START TEXT]\n{combined_text}\n[END TEXT]\n\n"
                    "Please analyze the above text and create a mapping with all possible paths, strictly following the specified format."
                )
            },
        ]
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
            max_tokens=2048
        )
        
        summary = response.choices[0].message['content'].strip()
        
        # Update phone record
        phone.summary = summary
        phone.summary_updated_at = timezone.now()
        # Проверяем наличие в очереди перед сохранением
        if not get_call_queue_model().objects.filter(phone_number=phone).exists():
            phone.status = 'completed'
        phone.save()
        
    except Exception as e:
        print(f"Error generating summary for phone {phone_id}: {str(e)}")

@shared_task
def schedule_recall():
    recall_interval = int(get_settings_model().get_value('recall_interval_hours', '24'))
    cutoff_time = timezone.now() - timezone.timedelta(hours=recall_interval)
    
    phones_to_recall = get_phone_number_model().objects.filter(
        models.Q(last_called_at__lte=cutoff_time) | 
        models.Q(last_called_at__isnull=True)
    )
    
    for phone in phones_to_recall:
        process_phone_number.delay(phone.id)

@shared_task
def process_unprocessed_recordings():
    try:
        CallRecord = get_call_record_model()
        check_interval = int(get_settings_model().get_value('recordings_check_interval', '5'))
        
        unprocessed_records = CallRecord.objects.filter(
            transcript__isnull=True,
            audio_file__isnull=False,
            created_at__lte=timezone.now() - timezone.timedelta(minutes=check_interval)
        )

        for record in unprocessed_records:
            try:
                # Расшифровываем аудио
                transcript = transcribe_audio(record.get_audio_file_path())
                
                if transcript:
                    # Сохраняем расшифровку
                    record.transcript = transcript
                    record.save()

                    # Проверяем статус всех транскрипций
                    record.phone_number.check_transcription_status()

                    # Генерируем summary только если хотя бы одна транскрипция успешна
                    if transcript != "Audio could not be transcribed":
                        generate_summary.delay(record.phone_number.id)

            except Exception as e:
                print(f"Ошибка при расшифровке записи {record.id}: {str(e)}")

    except Exception as e:
        print(f"Ошибка в process_unprocessed_recordings: {str(e)}")

def transcribe_audio(audio_file_path):
    """
    Транскрибация аудиофайла с использованием speech_recognition
    """
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(audio_file_path) as source:
            audio = recognizer.record(source)
        
        # Распознавание речи с русским языком
        transcript = recognizer.recognize_google(audio, language='ru-RU')
        return transcript
    except Exception as e:
        print(f"Ошибка при транскрибации {audio_file_path}: {str(e)}")
        return None

@shared_task
def process_call_queue():
    """
    Периодическая задача для обработки очереди звонков.
    Берет первый номер из очереди и инициирует звонок.
    """
    # Получаем первый номер из очереди
    queue_item = get_call_queue_model().objects.first()
    if queue_item:
        try:
            # Получаем номер телефона
            phone = queue_item.phone_number
            
            # Проверяем, не обрабатывается ли уже этот номер
            if phone.status == 'in_progress':
                print(f"Phone {phone.number} is already being processed, skipping")
                return
            
            # Удаляем запись из очереди
            queue_id = queue_item.id
            queue_item.delete()
            
            try:
                # Инициируем звонок
                phone.status = 'in_progress'
                phone.save()
                
                # Запускаем существующую логику звонка
                process_phone_number.delay(phone.id)
                
            except Exception as e:
                print(f"Error processing phone {phone.number}: {str(e)}")
                # В случае ошибки возвращаем номер в очередь
                phone.status = 'pending'
                phone.save()
                CallQueue.objects.create(
                    phone_number=phone,
                    priority=queue_item.priority
                )
            
        except Exception as e:
            print(f"Error processing queue item {queue_item.id}: {str(e)}")

@shared_task
def process_missing_summaries():
    """
    Регулярная задача для проверки и генерации саммари для номеров,
    у которых есть расшифрованные записи, но нет саммари
    """
    try:
        PhoneNumber = get_phone_number_model()
        CallRecord = get_call_record_model()
        Settings = get_settings_model()

        # Получаем интервал проверки из настроек, по умолчанию 5 минут
        check_interval = int(Settings.get_value('missing_summaries_check_interval', '5'))
        
        # Находим номера без саммари, но с расшифрованными записями
        numbers_without_summary = PhoneNumber.objects.filter(
            summary__isnull=True,  # нет саммари
            call_records__transcript__isnull=False  # есть расшифрованные записи
        ).distinct()  # убираем дубликаты

        for phone_number in numbers_without_summary:
            try:
                # Запускаем генерацию саммари
                generate_summary.delay(phone_number.id)
            except Exception as e:
                print(f"Ошибка при генерации Summary для номера {phone_number.number}: {str(e)}")

    except Exception as e:
        print(f"Ошибка в process_missing_summaries: {str(e)}")

@shared_task
def check_stuck_calls():
    """
    Проверяет и восстанавливает зависшие звонки.
    Звонок считается зависшим, если он находится в статусе 'in_progress' 
    дольше максимального времени звонка.
    """
    try:
        PhoneNumber = get_phone_number_model()
        Settings = get_settings_model()
        
        # Получаем максимальную длительность звонка из настроек
        max_call_duration = int(Settings.get_value('max_call_duration', '60'))
        
        # Находим все номера, которые "зависли" в статусе in_progress
        stuck_time = timezone.now() - timezone.timedelta(seconds=max_call_duration * 2)
        stuck_calls = PhoneNumber.objects.filter(
            status='in_progress',
            updated_at__lte=stuck_time
        )
        
        for phone in stuck_calls:
            try:
                print(f"Recovering stuck call for number: {phone.number}")
                # Возвращаем номер в очередь
                phone.status = 'pending'
                phone.save()
                phone.add_to_queue()
            except Exception as e:
                print(f"Error recovering stuck call {phone.number}: {str(e)}")
                
    except Exception as e:
        print(f"Error in check_stuck_calls: {str(e)}")

@shared_task
def check_completed_status():
    """
    Проверяет номера и устанавливает статус 'completed' если:
    1. Есть summary
    2. У всех записей есть транскрипция
    3. Номер не в очереди
    """
    try:
        PhoneNumber = get_phone_number_model()
        CallQueue = get_call_queue_model()
        
        # Получаем все номера, у которых есть summary
        phones = PhoneNumber.objects.filter(summary__isnull=False).exclude(status='completed')
        
        for phone in phones:
            try:
                # Проверяем наличие в очереди
                if CallQueue.objects.filter(phone_number=phone).exists():
                    continue
                
                # Проверяем все записи
                call_records = phone.call_records.all()
                if not call_records.exists():
                    continue
                    
                # Проверяем, что у всех записей есть транскрипция
                if call_records.filter(transcript__isnull=True).exists() or \
                   call_records.filter(transcript='').exists():
                    continue
                
                # Если все условия выполнены, устанавливаем статус "Готово"
                phone.status = 'completed'
                phone.save()
                print(f"Номер {phone.number} помечен как готовый")
                
            except Exception as e:
                print(f"Ошибка при обработке номера {phone.number}: {str(e)}")
                
    except Exception as e:
        print(f"Ошибка в check_completed_status: {str(e)}")

@shared_task
def check_failed_transcriptions():
    """
    Периодически проверяет записи и обновляет статусы номеров
    с неудачными транскрипциями
    """
    try:
        PhoneNumber = get_phone_number_model()
        phones = PhoneNumber.objects.exclude(status='failed')
        
        for phone in phones:
            phone.check_transcription_status()
            
    except Exception as e:
        print(f"Ошибка в check_failed_transcriptions: {str(e)}")


# Обновляем расписание Celery
app.conf.beat_schedule.update({
    'process-call-queue': {
        'task': 'phone_numbers.tasks.process_call_queue',
        'schedule': 20.0,  # каждые 20 секунд
    },
    'process-missing-summaries': {
        'task': 'phone_numbers.tasks.process_missing_summaries',
        'schedule': 300.0,  # каждые 5 минут
    },
    'check-stuck-calls': {
        'task': 'phone_numbers.tasks.check_stuck_calls',
        'schedule': 60.0,  # каждую минуту
    },
    'check-completed-status': {
        'task': 'phone_numbers.tasks.check_completed_status',
        'schedule': 60.0,  # Запускать каждую минуту
    },
    'check-failed-transcriptions': {
        'task': 'phone_numbers.tasks.check_failed_transcriptions',
        'schedule': 300.0,  # каждые 5 минут
    }
})
