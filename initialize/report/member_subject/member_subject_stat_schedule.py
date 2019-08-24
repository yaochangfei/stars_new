import os
import sys

from initialize.report.member_subject.init_member_subject_statistics_aggregate import do_init_member_stat

count = do_init_member_stat(just_return_count=True)

script_num = int(sys.argv[1])
skip_num = int(count / script_num)
limit_num, other = divmod(count, script_num)
if other:
    script_num += 1

print(count, script_num)
for i in range(script_num):
    os.system(
        'nohup python initialize/report/member_subject/init_member_subject_statistics_aggregate.py %s %s > '
        'init_member_subject_statistics_aggregate_%s.log 2>&1 &' % (skip_num * i, limit_num, i))
