#! /usr/bin/python

"""
对同一关卡，多次抽奖记录的人做处理

"""
import json

from db.models import MemberCheckPointHistory, Member
from motorengine.stages import MatchStage, GroupStage, LookupStage


def get_no_history_member():
    """
    获取没有历史记录的用户
    :return:
    """
    data = Member.sync_aggregate([
        MatchStage({'nick_name': '游客'}),
        LookupStage(MemberCheckPointHistory, 'cid', 'member_cid', 'history_list'),
        MatchStage({'history_list': []}),
        GroupStage('cid')
    ]).to_list(None)

    with open('./no-history-members.json', 'w', encoding='utf-8') as f:
        dist_list = json.dumps(list([d.id for d in data]), ensure_ascii=False)
        f.write(dist_list)


if __name__ == '__main__':
    member_list = get_no_history_member()
