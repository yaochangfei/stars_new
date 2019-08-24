#! /usr/bin/python


import json

from db import STATUS_RESULT_CHECK_POINT_WIN
from db.models import RaceGameCheckPoint, MemberCheckPointHistory
from motorengine.stages import MatchStage
from pymongo import ReadPreference


def export_history(race_cid):
    """

    :param race_cid:
    :return:
    """
    checkpoint_cids = RaceGameCheckPoint.sync_distinct('cid', {'race_cid': race_cid, 'redpkt_rule_cid': {'$ne': ''}})
    cursor = MemberCheckPointHistory.sync_aggregate([
        MatchStage({'check_point_cid': {'$in': checkpoint_cids}, 'status': STATUS_RESULT_CHECK_POINT_WIN}),
    ], read_preference=ReadPreference.PRIMARY).batch_size(2048)

    index = 0
    history_list = set()
    while True:
        try:
            data: MemberCheckPointHistory = cursor.next()
            history_list.add('%s-%s' % (data.check_point_cid, data.member_cid))

            print('has exec', index)
            index += 1
        except StopIteration:
            break

    with open('./history-%s.json' % race_cid, 'w', encoding='utf-8') as f:
        dist_list = json.dumps(list(history_list), ensure_ascii=False)
        f.write(dist_list)


if __name__ == '__main__':
    export_history('3040737C97F7C7669B04BC39A660065D') #'F742E0C7CA5F7E175844478D74484C29)
