#! /usr/bin/python3
from datetime import datetime

from db.models import MemberGameHistory, Member

member_game_history_list = MemberGameHistory.sync_find(
    {'updated_dt': {'$gte': datetime.now().replace(2019, 1, 29, 16, 30, 0, 0)}})

i, j = 1, 1
for his in member_game_history_list:
    # step1: 将段位减1
    if his.dan_grade == 12:
        # step2: 恢复原有钻石
        member = Member.sync_find_one({'cid': his.member_cid})
        member.diamond += 6000
        member.sync_save()
        j += 1

    his.dan_grade -= 1
    his.sync_save()
    i += 1

print('dan_grade changed count: %s' % i)
print('diamond changed count: %s' % j)
