#! /usr/bin/python3
import xlsxwriter
from datetime import datetime
from db.models import Member, MemberGameHistory, MemberDiamondDetail
from db import TYPE_DAN_GRADE_DICT, STATUS_RESULT_CHECK_POINT_DICT, SOURCE_MEMBER_DIAMOND_DICT
from commons.common_utils import datetime2str


def export_member_game_history(cond: dict):
    """
    获取该用户的对战历史
    :param cond:
    :return:
    """
    member = Member.sync_find_one(cond)
    if not member:
        return

    workbook = xlsxwriter.Workbook('%s的游戏历史明细.xlsx' % member.nick_name)
    worksheet = workbook.add_worksheet('game_history')

    history_list = MemberGameHistory.sync_find(
        {'member_cid': member.cid, 'created_dt': {'$gte': datetime.now().replace(2019, 1, 1, 0, 0, 0, 0)}}).sort(
        'created_dt').to_list(None)

    cols = ['时间', '所处段位', '状态', '钻石增减']
    for col_index, col_name in enumerate(cols):
        worksheet.write(0, col_index + 1, col_name)

    print(history_list)
    for index, his in enumerate(history_list):
        cols = [datetime2str(his.created_dt), TYPE_DAN_GRADE_DICT.get(his.dan_grade, str(his.dan_grade)),
                STATUS_RESULT_CHECK_POINT_DICT.get(his.status), str(his.result)]
        for col_index, col_name in enumerate(cols):
            worksheet.write(index + 1, col_index + 1, col_name)

    worksheet2 = workbook.add_worksheet('diamond_detail')
    details = MemberDiamondDetail.sync_find({'member_cid': member.cid}).sort('created_dt').to_list(None)
    cols = ['时间', '奖励来源', '奖励类型', '钻石增减']
    for col_index, col_name in enumerate(cols):
        worksheet2.write(0, col_index + 1, col_name)

    for index, detl in enumerate(details):
        cols = [datetime2str(detl.reward_datetime), SOURCE_MEMBER_DIAMOND_DICT.get(detl.source), detl.content,
                detl.diamond]
        for col_index, col_name in enumerate(cols):
            worksheet2.write(index + 1, col_index + 1, col_name)

    workbook.close()


if __name__ == '__main__':
    export_member_game_history({'cid': '5BD662460F7096703B331500F27C007C'})
