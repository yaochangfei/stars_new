# !/usr/bin/python

import time

from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from db.models import MemberGameHistory, MemberCheckPointHistory, Member
from enums import KEY_ALLOW_PROCESS_ACCURATE_STATISTICS, KEY_PREFIX_TASK_ACCURATE_STATISTICS
from tasks.instances.task_accurate_statistics import start_accurate_statistics


def get_fight_history_models():
    # 获取对战历史
    return MemberGameHistory.sync_find(dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)


def get_race_history_models():
    # 获取竞赛历史
    return MemberCheckPointHistory.sync_find(dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)


def deal_with_history():
    count = 1
    fight_history_list = get_fight_history_models()
    for index, fight_history in enumerate(fight_history_list):
        if fight_history:
            member = Member.sync_get_by_cid(fight_history.member_cid)
            if member:
                RedisCache.delete('%s_%s%s' % (KEY_PREFIX_TASK_ACCURATE_STATISTICS, member.cid, fight_history.cid))
                start_accurate_statistics.delay(fight_history, member)
                print(count, member.nick_name, fight_history.fight_datetime)
                if count % 20000 == 0:
                    print('sleeping 45s...')
                    time.sleep(45)
                count += 1

    race_history_list = get_race_history_models()
    for index, race_history in enumerate(race_history_list):
        if race_history:
            member = Member.sync_get_by_cid(race_history.member_cid)
            if member:
                RedisCache.delete('%s_%s%s' % (KEY_PREFIX_TASK_ACCURATE_STATISTICS, member.cid, race_history.cid))
                start_accurate_statistics.delay(race_history, member)
                print(count, member.nick_name, race_history.fight_datetime)
                if count % 20000 == 0:
                    print('sleeping 45s...')
                    time.sleep(45)
                count += 1


if __name__ == '__main__':
    RedisCache.delete(KEY_ALLOW_PROCESS_ACCURATE_STATISTICS)
    deal_with_history()
