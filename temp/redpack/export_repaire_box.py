#! /usr/bin/python


import json

from db.models import RedPacketBox, MemberCheckPointHistory
from motorengine.stages import MatchStage, LookupStage


def get_all_miss_history_box(race_cid):
    """
    获取没有历史记录的红包游标
    :param race_cid
    :return:
    """
    match_stage = MatchStage({'draw_status': 0})
    if race_cid:
        match_stage = MatchStage({'draw_status': 0, 'race_cid': race_cid})

    cursor = RedPacketBox.sync_aggregate(stage_list=[
        match_stage,
        LookupStage(MemberCheckPointHistory, as_list_name='history_list',
                    let={
                        'member_cid': '$member_cid',
                        'checkpoint': '$check_point_cid'
                    },
                    pipeline=[
                        {
                            '$match': {
                                '$expr': {
                                    '$and': [
                                        {'$eq': ['$member_cid', '$$member_cid']},
                                        {'$eq': ['$checkpoint_cid', '$$checkpoint']},
                                    ]
                                }
                            }
                        }]),
        MatchStage({'history_list': []}),
    ])

    index = 0
    repair_list = []
    while True:
        try:
            box = cursor.next()
            repair_list.append('%s-%s-%s' % (box.cid, box.member_cid, box.checkpoint_cid))
            index += 1
        except StopIteration:
            break

    with open('./repair-%s.json' % race_cid, 'w', encoding='utf-8') as f:
        dist_list = json.dumps(list(repair_list), ensure_ascii=False)
        f.write(dist_list)

    return index


if __name__ == '__main__':
    print('------ begin ------')
    # _cid = "3040737C97F7C7669B04BC39A660065D"  # 安徽
    _cid = "F742E0C7CA5F7E175844478D74484C29"
    print('发放红包总数:',
          RedPacketBox.sync_count({'race_cid': _cid, 'award_cid': {'$ne': None}, 'member_cid': {'$ne': None}}))

    print('缺少历史纪录的红包数量：', get_all_miss_history_box(_cid))
    print('------  end  ------')
