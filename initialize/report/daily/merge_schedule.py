import sys
import os
from initialize.report.daily.merge_stat import get_model_by_index

first = int(sys.argv[1])
secon = int(sys.argv[2])

model = get_model_by_index(secon)
count = model.sync_count({})

script_num = int(sys.argv[1])
skip_num = int(count / script_num)
limit_num, other = divmod(count, script_num)
if other:
    script_num += 1

print(count, script_num)
for i in range(script_num):
    os.system(
        'nohup python initialize/report/daily/merge_stat.py %s %s %s %s > daily_merge_sub_%s.log 2>&1 &' %
        (first, secon, skip_num * i, limit_num, i))
