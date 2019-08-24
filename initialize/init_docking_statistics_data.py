# !/usr/bin/python
# -*- coding:utf-8 -*-


import datetime

import settings
from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db.models import MemberGameHistory, MemberCheckPointHistory, DockingStatistics, Member
from enums import KEY_ALLOW_PROCESS_DOCKING_STATISTICS
from tasks.instances.task_docking_statistics import docking_statistics


def get_fight_history_models():
    # 获取对战历史
    return MemberGameHistory.sync_find(dict(record_flag=1)).batch_size(32)


def get_race_history_models():
    # 获取竞赛历史
    return MemberCheckPointHistory.sync_find(dict(record_flag=1)).batch_size(32)


def _get_docking_code(dt: datetime.datetime):
    """
    获取对接标识
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d000000')


def deal_with_history():
    fight_history_list = get_fight_history_models()
    count = 1
    for fight_history in fight_history_list:
        if fight_history:
            fight_datetime = fight_history.fight_datetime
            if fight_datetime:
                docking_code = _get_docking_code(fight_datetime)
                member = Member.sync_get_by_cid(fight_history.member_cid)
                if member:
                    ds = DockingStatistics.sync_find_one(dict(docking_code=docking_code, member_cid=member.cid))
                    if not ds:
                        ds = DockingStatistics(docking_code=docking_code, member_cid=member.cid)
                        ds.sync_save()
                    docking_statistics(fight_history, member, docking_code)
            print(count, fight_history.cid)
            count += 1

    race_history_list = get_race_history_models()
    for race_history in race_history_list:
        if race_history:
            race_datetime = race_history.fight_datetime
            if race_datetime:
                docking_code = _get_docking_code(race_datetime)
                member = Member.sync_get_by_cid(race_history.member_cid)
                if member:
                    ds = DockingStatistics.sync_find_one(dict(docking_code=docking_code, member_cid=member.cid))
                    if not ds:
                        ds = DockingStatistics(docking_code=docking_code, member_cid=member.cid)
                        ds.sync_save()
                    docking_statistics(race_history, member, docking_code)
            print(count, race_history.cid)
            count += 1


if __name__ == '__main__':
    RedisCache.set(KEY_ALLOW_PROCESS_DOCKING_STATISTICS, 0)
    deal_with_history()
