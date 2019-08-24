# !/usr/bin/python
# -*- coding:utf-8 -*-

from db.models import MemberStatisticInfo, RaceMapping


def repair(race_cid):
    new_member = MemberStatisticInfo.sync_distinct("member_cid", {'race_cid': race_cid, 'is_new_user': 1})
    total_member = MemberStatisticInfo.sync_distinct("member_cid", {'race_cid': race_cid})
    more = list(set(total_member) - set(new_member))
    print(more)
    # for member_cid in more:
    #     race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': member_cid})
    #     daily_code = format(race_mapping.created_dt, "%Y%m%d")
    #     member = MemberStatisticInfo.sync_find_one({'race_cid': race_cid, 'daily_code': daily_code})
    #     member.is_new_user = 1
    #     member.sync_save()


if __name__ == '__main__':
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D 扬州 DF1EDC30F120AEE93351A005DC97B5C1
    race_cid = "F742E0C7CA5F7E175844478D74484C29"
    repair(race_cid)
