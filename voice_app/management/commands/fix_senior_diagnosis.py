"""
장노년층(senior) 진단명을 xlsx 메타데이터 기준으로 보정하는 관리 명령어

앱에서 '목소리 문제 유무 = 있음'을 선택하면 diagnosis가 '없음'/'있음'으로 덮어써져
업로드되는 문제가 있어, xlsx의 '진단명'(정상/파킨슨병)으로 DB 값을 되돌립니다.

사용법:
    python manage.py fix_senior_diagnosis --xlsx <파일>              # 미리보기만 (DB 변경 없음)
    python manage.py fix_senior_diagnosis --xlsx <파일> --apply      # 앱 버그('없음'/'있음')만 보정
    python manage.py fix_senior_diagnosis --xlsx <파일> --apply --include-conflicts --fill-blank

보정 대상 구분:
    bug       : DB 값이 '없음'/'있음' (앱 버그)                 → 기본 보정
    conflict  : DB 값이 정상/파킨슨병인데 xlsx와 다름            → --include-conflicts
    blank     : DB 값이 비어 있는 파일 (주로 문장읽기 과제)       → --fill-blank
제외 대상:
    xlsx 안에서 ID가 중복되거나, xlsx 이름과 DB 이름이 다른 대상자 (ID 매핑 자체가 의심됨)

--apply 시 변경 전 값을 CSV로 백업합니다.
"""

import csv
import re
from collections import Counter, defaultdict
from datetime import datetime

import openpyxl
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from voice_app.models import AudioRecord

SHEET = '장노년층'
VALID_DIAGNOSES = {'정상', '파킨슨병'}
BUG_VALUES = {'없음', '있음'}


def _norm_id(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r'\s', '', str(value))


def _norm_name(value):
    return re.sub(r'\(.*?\)|\s', '', str(value or ''))


class Command(BaseCommand):
    help = '장노년층 진단명을 xlsx 기준으로 보정합니다 (기본: 미리보기)'

    def add_arguments(self, parser):
        parser.add_argument('--xlsx', required=True, help='기준 메타데이터 xlsx 경로')
        parser.add_argument('--apply', action='store_true', help='실제로 DB를 수정')
        parser.add_argument('--include-conflicts', action='store_true',
                            help='DB의 정상/파킨슨병 값이 xlsx와 다른 경우도 보정')
        parser.add_argument('--fill-blank', action='store_true',
                            help='diagnosis가 비어 있는 파일도 xlsx 값으로 채움')
        parser.add_argument('--backup', default=None, help='백업 CSV 경로 (기본: 자동 생성)')

    def handle(self, *args, **opts):
        xlsx_rows = self._load_xlsx(opts['xlsx'])

        id_count = Counter(r['id'] for r in xlsx_rows)
        db_names = defaultdict(Counter)
        for ident, name in AudioRecord.objects.filter(category='senior').values_list('identifier', 'name'):
            if ident and name:
                db_names[ident][_norm_name(name)] += 1

        plan = {'bug': [], 'conflict': [], 'blank': []}
        skipped = []
        for r in xlsx_rows:
            ident = r['id']
            if ident not in db_names:
                continue
            if id_count[ident] > 1:
                skipped.append((r, 'xlsx 내 중복 ID'))
                continue
            main_name = db_names[ident].most_common(1)[0][0]
            if main_name != _norm_name(r['name']):
                skipped.append((r, f'이름 불일치 (DB={main_name})'))
                continue

            current = Counter(
                (d or '') for d in AudioRecord.objects
                .filter(category='senior', identifier=ident).values_list('diagnosis', flat=True)
            )
            for value, n in current.items():
                if value == r['diagnosis']:
                    continue
                kind = 'blank' if value == '' else 'bug' if value in BUG_VALUES else 'conflict'
                plan[kind].append({**r, 'old': value, 'files': n})

        self._print_preview(plan, skipped, opts)

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('\n미리보기만 실행했습니다. DB는 변경되지 않았습니다. (--apply로 실행)'))
            return

        kinds = ['bug'] + (['conflict'] if opts['include_conflicts'] else []) + \
                (['blank'] if opts['fill_blank'] else [])
        self._apply([item for k in kinds for item in plan[k]], opts['backup'])

    def _load_xlsx(self, path):
        try:
            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            rows = list(wb[SHEET].iter_rows(values_only=True))
        except Exception as e:
            raise CommandError(f'xlsx 읽기 실패: {e}')
        header = rows[1]
        col = {k: header.index(k) for k in ('ID', '이름', '진단명')}
        out = []
        for line_no, row in enumerate(rows[2:], start=3):
            ident = _norm_id(row[col['ID']])
            diagnosis = str(row[col['진단명']] or '').strip()
            if row[col['이름']] and re.fullmatch(r'S\d+', ident) and diagnosis in VALID_DIAGNOSES:
                out.append({'row': line_no, 'id': ident, 'name': str(row[col['이름']]).strip(),
                            'diagnosis': diagnosis})
        return out

    def _print_preview(self, plan, skipped, opts):
        labels = {
            'bug': ('앱 버그 (없음/있음 → xlsx 진단명)', True),
            'conflict': ('값 충돌 (정상↔파킨슨병)', opts['include_conflicts']),
            'blank': ('빈 값 채우기', opts['fill_blank']),
        }
        for kind, (label, enabled) in labels.items():
            items = plan[kind]
            people = len({i['id'] for i in items})
            files = sum(i['files'] for i in items)
            mark = '적용 대상' if enabled else '적용 안 함 (옵션 필요)'
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\n[{label}] {people}명 / {files}개 파일 — {mark}'))
            if kind == 'blank':
                by_diag = Counter(i['diagnosis'] for i in items)
                self.stdout.write(f'  채울 값 분포: {dict(by_diag)}')
                continue
            for i in sorted(items, key=lambda x: x['row']):
                self.stdout.write(f"  row{i['row']:<4} {i['id']:<12} {i['name']:<6} "
                                  f"'{i['old']}' → '{i['diagnosis']}'  ({i['files']}개 파일)")

        self.stdout.write(self.style.MIGRATE_HEADING(f'\n[제외] {len(skipped)}명 — ID 매핑 확인 필요'))
        for r, reason in skipped:
            self.stdout.write(f"  row{r['row']:<4} {r['id']:<12} {r['name']:<6} {reason}")

    def _apply(self, items, backup_path):
        if not items:
            self.stdout.write('보정할 항목이 없습니다.')
            return
        backup_path = backup_path or f"diagnosis_backup_{datetime.now():%Y%m%d_%H%M%S}.csv"
        updated = 0
        with transaction.atomic(), open(backup_path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(['audio_id', 'identifier', 'old_diagnosis', 'new_diagnosis'])
            for i in items:
                qs = AudioRecord.objects.filter(category='senior', identifier=i['id'])
                qs = qs.filter(diagnosis__isnull=True) | qs.filter(diagnosis='') if i['old'] == '' \
                    else qs.filter(diagnosis=i['old'])
                for audio_id in qs.values_list('id', flat=True):
                    writer.writerow([audio_id, i['id'], i['old'], i['diagnosis']])
                updated += qs.update(diagnosis=i['diagnosis'])
        self.stdout.write(self.style.SUCCESS(f'\n{updated}개 파일 보정 완료. 백업: {backup_path}'))
