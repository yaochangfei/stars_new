# !/usr/bin/python
# -*- coding:utf-8 -*-
from commons.common_utils import str2datetime
from db.models import MemberStatisticInfo, RaceMapping, MemberCheckPointHistory
from initialize.incremental.member_statistic_1 import task_one_day
from motorengine.stages import MatchStage, GroupStage

from db.models import Race

from initialize.incremental.member_statistic import get_date_range, clear_redis_cache
from tasks.instances.task_member_statistics_single import start_single_member_statistics


def test(race_cid):
    member_cid_list = MemberStatisticInfo.sync_distinct("member_cid", {'race_cid': race_cid, 'is_new_user': 1})
    list2 = MemberStatisticInfo.sync_distinct('member_cid', {'race_cid': race_cid})
    cursor2 = MemberStatisticInfo.sync_find({'race_cid': race_cid})
    print(len(member_cid_list))
    print(len(list2))
    count = 0
    count1 = 0
    dailiy = set()
    for member in cursor2:
        count += 1
        if member.member_cid not in member_cid_list:
            count1 += 1
            print('-----------------------')
            dailiy.add(member.daily_code)
            print(member.daily_code, member.member_cid, member.is_new_user, member.draw_red_packet_amount)
            race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': member.member_cid})
            print(11, race_mapping.cid, format(race_mapping.created_dt, "%Y%m%d"), race_mapping.updated_dt)
            current_date = str2datetime(member.daily_code, '%Y%m%d').replace(hour=0, minute=0, second=0, microsecond=0)
            has_history = MemberCheckPointHistory.sync_find_one(
                {'member_cid': member.member_cid,
                 'created_dt': {'$lt': current_date}})
            if has_history:
                print(222, has_history)
            else:
                print(None)
    print('total', count)
    print('no', count1)
    temp = list(dailiy)
    temp.sort()
    print(temp)
    return temp


def test2(race_cid):
    total = MemberStatisticInfo.sync_count({'race_cid': race_cid, 'is_new_user': 1})
    cursor = MemberStatisticInfo.sync_aggregate([
        MatchStage({'race_cid': race_cid, 'is_new_user': 1}),
        GroupStage('member_cid', count={'$sum': 1}),
        MatchStage({'count': {'$gt': 1}})
    ])
    for stat in cursor:
        print(stat.id, stat.count)
        cursor1 = MemberStatisticInfo.sync_find({'member_cid': stat.id})
        for s in cursor1:
            print(s.daily_code, s.is_new_user, s.is_special_user)
    print(total)


def deal_history_data(race_cid, daily_code_list):
    """
    用于生成中间表处理历史数据(截止到昨天)
    :return:
    """
    race = Race.sync_find_one({'cid': race_cid})
    if not daily_code_list:
        daily_code_list = get_date_range(race.start_datetime)
    print(daily_code_list)
    clear_redis_cache(race_cid)
    for daily_code in daily_code_list:
        start_single_member_statistics.delay(race_cid, daily_code)


def deal_history_data_no_task(race_cid, daily_code_list):
    """
    用于生成中间表处理历史数据(截止到昨天)
    :return:
    """
    race = Race.sync_find_one({'cid': race_cid})
    if not daily_code_list:
        daily_code_list = get_date_range(race.start_datetime)
    print(daily_code_list)
    clear_redis_cache(race_cid)
    for daily_code in daily_code_list:
        task_one_day(race_cid, daily_code)


if __name__ == '__main__':
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D 扬州 DF1EDC30F120AEE93351A005DC97B5C1
    test('F742E0C7CA5F7E175844478D74484C29')
    # test2('F742E0C7CA5F7E175844478D74484C29')
    # race_cid_list = ['CA755167DEA9AA89650D11C10FAA5413', '3040737C97F7C7669B04BC39A660065D',
    #                  'F742E0C7CA5F7E175844478D74484C29', 'DF1EDC30F120AEE93351A005DC97B5C1']
    # daily_code_list = ['20190723', '20190717', '20190724', '20190715', '20190720', '20190714', '20190719', '20190722',
    #                    '20190721', '20190725', '20190712', '20190718', '20190713', '20190716']
    # for race_cid in race_cid_list:
    #     daily_code_list = test(race_cid)
    #     print(daily_code_list)
        # if daily_code_list:
        #     deal_history_data(race_cid, daily_code_list)
