#! /usr/bin/python


import json

from db.models import RedPacketBox
from pymongo import ReadPreference


def export_redpacket(race_cid):
    """

    :param race_cid:
    :return:
    """
    box_list = set()

    cursor = RedPacketBox.sync_find(
        {'race_cid': race_cid, 'award_cid': {'$ne': None}, 'member_cid': {"$ne": None}},
        read_preference=ReadPreference.PRIMARY).batch_size(2048)

    index = 0
    while True:
        try:
            data: RedPacketBox = cursor.next()
            box_list.add('%s-%s' % (data.checkpoint_cid, data.member_cid))
            index += 1
            print('has exec', index)
        except StopIteration:
            break

    with open('./box-%s.json' % race_cid, 'w', encoding='utf-8') as f:
        dist_list = json.dumps(list(box_list), ensure_ascii=False)
        f.write(dist_list)


if __name__ == '__main__':
    export_redpacket('F742E0C7CA5F7E175844478D74484C29') #'3040737C97F7C7669B04BC39A660065D)
