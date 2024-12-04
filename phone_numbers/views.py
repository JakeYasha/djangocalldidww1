from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, UpdateView, CreateView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.db import IntegrityError, transaction
from .models import PhoneNumber, Settings, CallRecord, CallQueue
from .tasks import process_phone_number
import json
import requests
import os
from django.conf import settings
import logging
logger = logging.getLogger(__name__)

class PhoneNumberListView(ListView):
    model = PhoneNumber
    template_name = 'phone_numbers/list.html'
    context_object_name = 'phone_numbers'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['settings'] = Settings.objects.all()
        return context

class PhoneNumberCreateView(CreateView):
    model = PhoneNumber
    template_name = 'phone_numbers/create.html'
    fields = ['number']
    success_url = reverse_lazy('phone_number_list')
    
    def form_valid(self, form):
        try:
            # Проверяем, существует ли уже такой номер
            number = form.cleaned_data['number']
            phone_number = PhoneNumber.objects.filter(number=number).first()
            
            if phone_number:
                # Если номер существует, просто добавляем его в очередь
                phone_number.add_to_queue()
                messages.success(self.request, f'Номер телефона {phone_number.number} добавлен в очередь.')
                return redirect(self.success_url)
            
            # Создаем транзакцию для атомарного создания номера и записи
            with transaction.atomic():
                # Создаем номер
                self.object = form.save()
                # Создаем первую запись звонка
                self.object.call_records.create()
                # Добавляем в очередь
                self.object.add_to_queue()
                
            messages.success(self.request, f'Номер телефона {self.object.number} успешно добавлен и поставлен в очередь.')
            return redirect(self.success_url)
            
        except Exception as e:
            messages.error(self.request, f'Произошла ошибка при добавлении номера: {str(e)}')
            return self.form_invalid(form)

def extract_phone_numbers(text):
    """
    Простой парсер для извлечения телефонных номеров из текста
    """
    import re
    # Ищем номера в форматах: +1234567890, 1234567890, +1-234-567-890 и т.д.
    pattern = r'[\+]?[0-9][0-9\-\(\)]{8,}[0-9]'
    numbers = re.findall(pattern, text)
    # Очищаем номера от всех символов кроме цифр и +
    cleaned_numbers = []
    for number in numbers:
        cleaned = ''.join(char for char in number if char.isdigit() or char == '+')
        if len(cleaned) >= 10:  # Проверяем минимальную длину номера
            cleaned_numbers.append(cleaned)
    return cleaned_numbers


def phone_number_create_multiple(request):
    if request.method == 'POST':
        raw_numbers = request.POST.get('phone_numbers', '')
        
        # Отправляем запрос к ChatGPT для обработки номеров
        try:
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a phone number parser. Extract all phone numbers from the input text and return them as a JSON array of strings. Each number should contain only digits, no spaces or special characters. Example output: [\"79991234567\",\"78889999999\"]"
                        },
                        {
                            "role": "user",
                            "content": raw_numbers
                        }
                    ]
                }
            )
            
            if response.status_code == 200:
                try:
                    # Получаем массив номеров из ответа ChatGPT
                    numbers = json.loads(response.json()['choices'][0]['message']['content'])
                    print("\n\n\n\n")
                    print(numbers)
                    print("\n\n\n\n")
                    added_count = 0
                    duplicate_count = 0
                    
                    for number in numbers:
                        try:
                            # Пытаемся создать новый номер
                            phone = PhoneNumber.objects.create(number=number)
                            # Запускаем задачу обзвона для нового номера
                            phone.add_to_queue()
                            added_count += 1
                        except IntegrityError:
                            # Если номер уже существует, вызываем метод recall()
                            phone = PhoneNumber.objects.get(number=number)
                            phone.recall()
                            duplicate_count += 1
                    
                    messages.success(request, 
                        f'Добавлено {added_count} новых номеров. '
                        f'{duplicate_count} номеров отправлено на повторный обзвон.')
                    
                except (json.JSONDecodeError, KeyError, IndexError) as e:
                    messages.error(request, f'Ошибка при обработке ответа от ChatGPT: {str(e)}')
            else:
                messages.error(request, f'Ошибка при обращении к ChatGPT: {response.status_code}')
        except Exception as e:
            messages.error(request, f'Произошла ошибка: {str(e)}')
    
    return render(request, 'phone_numbers/create_multiple.html')


class PhoneNumberUpdateView(UpdateView):
    model = PhoneNumber
    template_name = 'phone_numbers/create.html'  # Можно использовать тот же шаблон, что и для создания
    fields = ['number', 'summary']  # Добавляем возможность редактировать summary
    success_url = reverse_lazy('phone_number_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Phone number {self.object.number} updated successfully.')
        return response

class SettingsUpdateView(UpdateView):
    model = Settings
    template_name = 'phone_numbers/settings.html'
    fields = ['value', 'description']
    success_url = reverse_lazy('phone_number_list')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Setting {self.object.key} updated successfully.')
        return response

def phone_number_detail(request, number):
    """Отображение деталей номера телефона"""
    try:
        phone_number = get_object_or_404(PhoneNumber, number=number)
        context = {
            'phone_number': phone_number,
            'MEDIA_URL': settings.MEDIA_URL,
        }
        return render(request, 'phone_numbers/phone_number_detail.html', context)
    except:
        messages.error(request, f'Номер телефона {number} не найден.')
        return redirect('phone_number_list')

def recall_phone_number(request, number):
    """Повторный набор номера"""
    try:
        phone_number = get_object_or_404(PhoneNumber, number=number)
        phone_number.recall(reset_counter=True)
        messages.success(request, f'Номер {number} добавлен в очередь для повторного набора.')
    except:
        messages.error(request, f'Номер телефона {number} не найден.')
    return redirect('phone_number_list')

def queue_count(request):
    """API endpoint для получения количества номеров в очереди"""
    count = CallQueue.objects.count()
    return JsonResponse({'count': count})
