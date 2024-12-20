# Generated by Django 4.2.7 on 2024-12-01 14:21

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PhoneNumber',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('number', models.CharField(max_length=20, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('last_called_at', models.DateTimeField(blank=True, null=True)),
                ('summary', models.TextField(blank=True)),
                ('summary_updated_at', models.DateTimeField(blank=True, null=True)),
                ('processing_time', models.DurationField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Settings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=50, unique=True)),
                ('value', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
            ],
            options={
                'verbose_name_plural': 'Settings',
            },
        ),
        migrations.CreateModel(
            name='CallRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('audio_file', models.FileField(upload_to='recordings/')),
                ('transcript', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('phone_number', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='call_records', to='phone_numbers.phonenumber')),
            ],
        ),
    ]
