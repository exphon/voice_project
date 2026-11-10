import io
import json
import os
import shutil
import tempfile
import wave
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from .models import AudioRecord


def _wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b'\x00\x00' * 1600)
    return buf.getvalue()


class SeniorUploadMetadataFileTest(TestCase):
    """앱은 그림이름대기 메타데이터를 'metadata_json' 키의 '파일'로 보낸다."""

    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.media, ignore_errors=True)
        self.metadata = {
            'metainfo_senior': {'identifier': 'S99999', 'name': '테스트', 'gender': '여', 'diagnosis': '정상'},
            'task_info': {'task_type': 'picture_button', 'task_description': '그림 버튼 이름대기 과제'},
        }

    def _upload(self):
        with override_settings(MEDIA_ROOT=self.media), \
                mock.patch('voice_app.views.transcribe_audio_task'):
            return self.client.post('/api/senior/upload/', {
                'file': SimpleUploadedFile('rec.wav', _wav_bytes(), content_type='audio/wav'),
                'metadata_json': SimpleUploadedFile(
                    'senior_picture_button_img00_metadata.json',
                    json.dumps(self.metadata, ensure_ascii=False).encode('utf-8'),
                    content_type='application/json'),
                'identifier': 'S99999',
                'task_type': 'picture_button',
            })

    def test_metadata_file_is_written_to_json(self):
        response = self._upload()
        self.assertLess(response.status_code, 300, response.content[:500])

        record = AudioRecord.objects.get(identifier='S99999')
        json_path = os.path.join(self.media, os.path.splitext(record.audio_file.name)[0] + '.json')
        self.assertGreater(os.path.getsize(json_path), 0, '메타데이터 json이 빈 파일로 저장됨')

        with open(json_path, encoding='utf-8') as f:
            saved = json.load(f)
        self.assertEqual(saved['client_metadata'], self.metadata)
        self.assertIn('metadata_path', record.category_specific_data)
