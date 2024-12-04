from django.urls import path
from .views import (
    PhoneNumberListView, 
    PhoneNumberCreateView, 
    PhoneNumberUpdateView,
    SettingsUpdateView,
    phone_number_detail,
    recall_phone_number,
    phone_number_create_multiple,
    queue_count
)

urlpatterns = [
    path('', PhoneNumberListView.as_view(), name='phone_number_list'),
    path('create/', PhoneNumberCreateView.as_view(), name='phone_number_create'),
    path('create/multiple/', phone_number_create_multiple, name='phone_number_create_multiple'),
    path('<int:pk>/update/', PhoneNumberUpdateView.as_view(), name='phone_number_update'),
    path('settings/<int:pk>/', SettingsUpdateView.as_view(), name='settings_update'),
    path('number/<str:number>/', phone_number_detail, name='phonenumber_detail'),
    path('number/<str:number>/recall/', recall_phone_number, name='phonenumber_recall'),
    path('api/queue-count/', queue_count, name='queue_count'),
]
