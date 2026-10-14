"""Check native HTTP semantics and task durability across a native process restart."""
import argparse
import json
import sys
import uuid
from pathlib import Path

from compare_runtimes import COMPOSE, suite

sys.path.insert(0, str(suite.ROOT / 'scripts'))
from verify_api import verify, request

def check(output):
    suite.API = 'team-tasks-compare-native-1'
    suite.command(COMPOSE+['stop','jvm','native'],check=False)
    suite.command(COMPOSE+['up','-d','native'])
    suite.wait_ready()
    result = {'httpAcceptance':verify(suite.BASE)}
    team = 8_000_000_000_000 + uuid.uuid4().int % 100_000_000
    before = request(suite.BASE,'POST','/tasks', {'teamId':team,'name':'native restart proof','description':'persist all fields'},expected=(201,))
    try:
        suite.command(COMPOSE+['restart','native'])
        suite.wait_ready()
        after = request(suite.BASE,'GET',f"/tasks/{before['id']}",expected=(200,))
        assert before == after, (before,after)
        result['restartPersistence'] = {'passed':True,'before':before,'after':after}
    finally:
        request(suite.BASE,'DELETE',f"/tasks/{before['id']}",expected=(204,))
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='performance/results/jvm-native-comparison/native-validation.json')
    check(parser.parse_args().output)
