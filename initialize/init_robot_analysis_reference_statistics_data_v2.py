# !/usr/bin/python

import time

from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from db.models import MemberGameHistory, MemberCheckPointHistory, Member
from enums import KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS
from tasks.instances.task_robot_analysis_reference import task_robot_analysis_reference_statistics


def get_fight_history_models():
    # 获取对战历史
    return MemberGameHistory.sync_find(dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)


def get_race_history_models():
    # 获取竞赛历史
    return MemberCheckPointHistory.sync_find(dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)


def deal_with_history():
    fight_history_list = get_fight_history_models()
    count = 1
    for fight_history in fight_history_list:
        if fight_history:
            member = Member.sync_get_by_cid(fight_history.member_cid)
            if member:
                task_robot_analysis_reference_statistics.delay(fight_history, member)
                print(count, member.nick_name, fight_history.fight_datetime)
                if count % 20000 == 0:
                    print('sleeping 30s...')
                    time.sleep(45)
                count += 1

    race_history_list = get_race_history_models()
    for race_history in race_history_list:
        if race_history:
            member = Member.sync_get_by_cid(race_history.member_cid)
            if member:
                task_robot_analysis_reference_statistics.delay(race_history)
                print(count, member.nick_name, race_history.fight_datetime)
                if count % 20000 == 0:
                    print('sleeping 30s...')
                    time.sleep(45)
                count += 1


if __name__ == '__main__':
    RedisCache.set(KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS, 0)
    deal_with_history()
