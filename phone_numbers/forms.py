from django import forms
from django.forms import formset_factory
from .models import PhoneNumber

class PhoneNumberForm(forms.Form):
    number = forms.CharField(
        max_length=20, 
        widget=forms.TextInput(attrs={
            'placeholder': 'Введите номер телефона',
            'class': 'form-control'
        }),
        help_text='Введите номер телефона в международном формате'
    )

    def clean_number(self):
        """
        Очистка и валидация номера телефона
        """
        number = self.cleaned_data['number']
        
        # Удаляем все нецифровые символы, кроме '+'
        cleaned_num = ''.join(char for char in number if char.isdigit() or char == '+')
        
        # Проверяем длину и формат номера
        if len(cleaned_num) >= 10 and cleaned_num.startswith('+'):
            return cleaned_num
        else:
            raise forms.ValidationError('Некорректный номер телефона')

class PhoneNumberMultipleForm(forms.Form):
    """
    Форма для добавления нескольких номеров с динамическим количеством полей
    """
    number_count = forms.IntegerField(
        initial=3,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': 1,
            'max': 10
        }),
        help_text='Количество номеров для добавления (от 1 до 10)'
    )

    def __init__(self, *args, **kwargs):
        """
        Динамическое создание полей для ввода номеров
        """
        super().__init__(*args, **kwargs)
        
        # Получаем количество полей из cleaned_data или initial
        number_count = self.data.get('number_count', 
                                     self.initial.get('number_count', 3))
        
        # Создаем динамические поля для номеров
        for i in range(1, int(number_count) + 1):
            self.fields[f'number_{i}'] = forms.CharField(
                max_length=20,
                required=False,
                widget=forms.TextInput(attrs={
                    'placeholder': f'Номер {i}',
                    'class': 'form-control'
                })
            )

    def clean(self):
        """
        Валидация и очистка всех введенных номеров
        """
        cleaned_data = super().clean()
        number_count = int(cleaned_data.get('number_count', 3))
        
        valid_numbers = []
        for i in range(1, number_count + 1):
            number_key = f'number_{i}'
            number = cleaned_data.get(number_key, '').strip()
            
            if number:
                try:
                    # Удаляем все нецифровые символы, кроме '+'
                    cleaned_num = ''.join(char for char in number if char.isdigit() or char == '+')
                    
                    # Проверяем длину и формат номера
                    if len(cleaned_num) >= 10 and cleaned_num.startswith('+'):
                        valid_numbers.append(cleaned_num)
                    else:
                        self.add_error(number_key, 'Некорректный номер телефона')
                except Exception as e:
                    self.add_error(number_key, str(e))
        
        cleaned_data['valid_numbers'] = valid_numbers
        return cleaned_data

    def save(self):
        """
        Сохранение валидных номеров телефонов
        """
        created_numbers = []
        valid_numbers = self.cleaned_data.get('valid_numbers', [])
        
        for number in valid_numbers:
            # Создаем номер, если его еще нет
            phone_number, created = PhoneNumber.objects.get_or_create(
                number=number
            )
            if created:
                created_numbers.append(phone_number)
        
        return created_numbers
