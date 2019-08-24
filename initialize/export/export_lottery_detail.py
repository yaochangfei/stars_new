#! /usr/bin/python3
from datetime import datetime

import xlsxwriter
from commons.common_utils import datetime2str
from db.enums import STATUS_REDPACKET_AWARD_DICT
from db.models import Race, Member, RedPacketBox, RedPacketItemSetting, RaceGameCheckPoint, RaceMapping
from motorengine.stages import MatchStage, LookupStage
from pymongo import ReadPreference


def export_lottery_detail(race_cid: str):
    """

    :param race_cid:
    :return:
    """

    race = Race.sync_find_one({'cid': race_cid})
    workbook = xlsxwriter.Workbook('%s中奖人员名单.xlsx' % race.title)
    worksheet = workbook.add_worksheet()

    _b_dt = datetime.now().replace(2019, 5, 20, 0, 0, 0, 0)
    _e_dt = datetime.now()

    cursor = RedPacketBox.sync_aggregate(
        [MatchStage({'draw_dt': {'$gt': _b_dt, '$lt': _e_dt}, 'draw_status': 0, 'race_cid': race_cid}),
         LookupStage(Member, 'member_cid', 'cid', 'member_list'),
         # LookupStage(RaceMapping, 'member_cid', 'member_cid', 'map_list'),
         # LookupStage(RedPacketItemSetting, 'award_cid', 'cid', 'item_list')
         ],
        read_preference=ReadPreference.PRIMARY).batch_size(128)
    cols = ['序号', '时间', '用户OPENID', '微信昵称', '奖品', '奖励金额', '领取状态', '省', '市', '区', '领取时间', '关卡序号', '获奖时间', '答题时间', '红包id']
    for col_index, col_name in enumerate(cols):
        worksheet.write(0, col_index, col_name)

    _row = 1
    while True:
        try:
            box = cursor.next()
            worksheet.write_number(_row, 0, _row)
            worksheet.write_string(_row, 1, datetime2str(box.draw_dt))
            worksheet.write_string(_row, 2, box.member_list[0].open_id if box.member_list else '未知')
            worksheet.write_string(_row, 3, box.member_list[0].nick_name if box.member_list else '未知')
            # worksheet.write_string(_row, 4, box.item_list[0].title if box.item_list else '未知')
            worksheet.write_number(_row, 5, box.award_amount)
            worksheet.write_string(_row, 6, STATUS_REDPACKET_AWARD_DICT.get(box.draw_status))

            # if box.map_list:
            #     worksheet.write_string(_row, 7, box.map_list[0].auth_address.get('province', ''))
            #     worksheet.write_string(_row, 8, box.map_list[0].auth_address.get('city', ''))
            #     worksheet.write_string(_row, 9, box.map_list[0].auth_address.get('district', ''))

            worksheet.write_string(_row, 10, datetime2str(box.request_dt))

            checkpt = RaceGameCheckPoint.sync_get_by_cid(box.checkpoint_cid)
            if checkpt:
                worksheet.write_number(_row, 11, checkpt.index)

            worksheet.write_string(_row, 12, datetime2str(box.draw_dt))
            # his = MemberCheckPointHistory.sync_find_one(
            #     {'member_cid': box.member_cid, 'check_point_cid': box.checkpoint_cid})
            # if his:
            #     worksheet.write_string(_row, 13, datetime2str(his.created_dt))

            worksheet.write_string(_row, 14, box.cid)

            print('has exec', _row)
            _row += 1
        except StopIteration:
            break

    workbook.close()


if __name__ == '__main__':
    export_lottery_detail('F742E0C7CA5F7E175844478D74484C29')  # '3040737C97F7C7669B04BC39A660065D)
