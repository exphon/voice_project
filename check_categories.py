#!/usr/bin/env python
import os
import django

# Django 설정
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'voice_project.settings')
django.setup()

from voice_app.models import AudioRecord

print('Total records:', AudioRecord.objects.count())
print('Category counts:')
for cat in ['child', 'senior', 'atypical', 'auditory', 'normal']:
    count = AudioRecord.objects.filter(category=cat).count()
    print(f'{cat}: {count}')

print('\nFirst 5 records with their file paths:')
for record in AudioRecord.objects.all()[:5]:
    print(f'ID: {record.id}, Category: {record.category}, File: {record.audio_file.name}')
