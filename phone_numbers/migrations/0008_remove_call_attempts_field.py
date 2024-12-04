from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('phone_numbers', '0007_remove_phonenumber_call_attemptsed'),  # замените на имя последней миграции
    ]

    operations = [
        migrations.RunSQL(
            # SQL для удаления колонки
            sql='ALTER TABLE phone_numbers_phonenumber DROP COLUMN call_attempts;',
            # SQL для отката изменений
            reverse_sql='ALTER TABLE phone_numbers_phonenumber ADD COLUMN call_attempts integer NOT NULL DEFAULT 0;'
        ),
    ]