"""Read native Gatling report data without chart-library dependencies."""
import json
import re

def native_stats(path):
    text=path.read_text(encoding='utf-8').split('function fillStats',1)[0]
    text=text.removeprefix('var stats = ').strip().rstrip(';')
    text=re.sub(r'"(?:\\.|[^"\\])*"|([A-Za-z_$][\w$]*)\s*:',
                lambda m:json.dumps(m.group(1))+':' if m.group(1) else m.group(0),text)
    return json.loads(text)
