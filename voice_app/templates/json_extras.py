from django import template
import json

register = template.Library()

@register.filter
def json_script(value, element_id):
    """JSON 데이터를 스크립트 태그로 안전하게 출력"""
    json_str = json.dumps(value)
    return f'<script id="{element_id}" type="application/json">{json_str}</script>'