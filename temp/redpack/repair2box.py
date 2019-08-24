#! /usr/bin/python

"""
对同一关卡，多次抽奖记录的人做处理

"""
import copy
import json

from db.models import RedPacketBox
from motorengine.stages import MatchStage, GroupStage
from pymongo import ReadPreference


def repair_records(race_cid):
    """
    单个关卡中存在多个抽奖的记录
    :param race_cid:
    :return:
    """

    cursor = RedPacketBox.sync_aggregate([
        MatchStage({'race_cid': race_cid, 'member_cid': {'$ne': None}}),
        GroupStage({'member_cid': '$member_cid', 'checkpoint_cid': '$checkpoint_cid'}, count={'$sum': 1},
                   box_list={'$push': '$cid'}),
        MatchStage({'count': {'$gte': 2}})
    ], read_preference=ReadPreference.PRIMARY, allowDiskUse=True).batch_size(256)

    with open('./no-history-members.json', 'r') as f:
        member_list = json.load(f)

    index = count = 0
    ck_member_map = {}
    fail_list = []
    while True:
        try:
            data = cursor.next()

            box_list = RedPacketBox.sync_find({'cid': {'$in': data.box_list}}).to_list(None)

            yes_list = list(filter(lambda x: x.award_cid is not None, box_list))  # draw_status --> award_cid
            noo_list = list(filter(lambda x: x.award_cid is None, box_list))

            # 对于多余的记录，直接改给没有历史记录的游客
            if len(yes_list) == 0:
                noo_list.pop()

            elif len(yes_list) == 1:
                pass

            elif len(yes_list) >= 2:
                noo_list += list(filter(lambda x: x.draw_status == 1, yes_list))

            for noo_box in noo_list:
                try:
                    _m_list = ck_member_map.get(noo_box.checkpoint_cid)
                    if _m_list == 'empty':
                        fail_list.append(noo_box.cid)
                        continue

                    if not _m_list:
                        _m_list = copy.deepcopy(member_list)

                    count += 1

                    while True:
                        try:
                            fit_cid = _m_list.pop()
                            if RedPacketBox.sync_count(
                                    {'checkpoint_cid': noo_box.checkpoint_cid, 'member_cid': fit_cid},
                                    read_preference=ReadPreference.PRIMARY) == 0:
                                break
                        except IndexError:
                            _m_list = 'empty'
                            print('empty: %s' % noo_box.checkpoint_cid)
                            break

                    ck_member_map[noo_box.checkpoint_cid] = _m_list
                    if _m_list == 'empty':
                        continue

                    if not fit_cid:
                        fail_list.append(noo_box.cid)
                        continue

                    noo_box.member_cid = fit_cid
                    noo_box.award_cid = None
                    noo_box.award_amount = 0
                    noo_box.award_msg = None
                    noo_box.needless['repair_flag'] = 1

                    noo_box.sync_save()
                    index += 1
                    print('has done', index)
                except IndexError:
                    fail_list.append(noo_box.cid)
        except StopIteration:
            break

    print(index, count)
    assert fail_list == [], 'fail list not empty, length: %s' % len(fail_list)


if __name__ == '__main__':
    _cid = "3040737C97F7C7669B04BC39A660065D"  # 安徽
    # _cid = 'F742E0C7CA5F7E175844478D74484C29'
    repair_records(_cid)
