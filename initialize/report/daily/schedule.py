import os
import sys

from db.models import MemberGameHistory

count = MemberGameHistory.sync_count({})
script_num = int(sys.argv[1])
skip_num = int(count / script_num)
limit_num, other = divmod(count, script_num)
if other:
    script_num += 1

print(count, script_num)
for i in range(script_num):
    os.system(
        'nohup python initialize/report/daily/init_sub.py %s %s %s > daily_init_sub_%s.log 2>&1 &' % (
            i, skip_num * i, limit_num, i))
