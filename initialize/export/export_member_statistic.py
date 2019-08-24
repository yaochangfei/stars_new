# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime

import xlsxwriter

from db.models import MemberStatisticInfo, Race
from motorengine import ASC
from motorengine.stages import MatchStage, GroupStage, SortStage


def export_member_to_excel(workbook, race_cid, s_daily_code=None, e_daily_code=None):
    """
    会员信息导入
    :param workbook:
    :param race_cid:
    :param s_daily_code:
    :param e_daily_code:
    :return:
    """
    match = MatchStage({'race_cid': race_cid})
    if s_daily_code and e_daily_code:
        match['daily_code'] = {'$gte': s_daily_code, '$lte': e_daily_code}
    group = GroupStage({'member_cid': '$member_cid', 'race_cid': '$race_cid'},
                       nick_name={'$first': '$nick_name'},
                       open_id={'$first': '$open_id'},
                       province={'$first': '$province'},
                       city={'$first': '$city'},
                       district={'$first': '$district'},
                       mobile={'$first': '$mobile'},
                       check_point_index={'$max': '$check_point_index'},
                       is_final_passed={'$max': '$is_final_passed'},
                       first_time_login={'$first': '$first_time_login'},
                       enter_times={'$sum': '$enter_times'},
                       draw_red_packet_count={'$sum': '$draw_red_packet_count'},
                       draw_red_packet_amount={'$sum': '$draw_red_packet_amount'},
                       )
    sort_stage = SortStage([('first_time_login', ASC)])
    exported_member_list = MemberStatisticInfo.sync_aggregate([match, group, sort_stage], allowDiskUse=True).to_list(
        None)
    sheet = workbook.add_worksheet("会员信息")
    sheet.merge_range(0, 0, 0, 1, '昵称')
    sheet.merge_range(0, 2, 0, 3, 'open_id')
    sheet.merge_range(0, 4, 0, 5, '城市')
    sheet.merge_range(0, 6, 0, 7, '区县')
    sheet.merge_range(0, 8, 0, 9, '手机号码')
    sheet.merge_range(0, 10, 0, 11, '答题次数')
    sheet.merge_range(0, 12, 0, 13, '当前关卡数')
    sheet.merge_range(0, 14, 0, 15, '第一次进入小程序时间')
    sheet.merge_range(0, 16, 0, 17, '领取红包数')
    sheet.merge_range(0, 18, 0, 19, '领取红包金额')

    for index, member_info in enumerate(exported_member_list):
        row = index + 1
        sheet.merge_range(row, 0, row, 1, member_info.nick_name)
        sheet.merge_range(row, 2, row, 3, member_info.open_id)
        sheet.merge_range(row, 4, row, 5, member_info.city)
        sheet.merge_range(row, 6, row, 7, member_info.district)
        sheet.merge_range(row, 8, row, 9, member_info.mobile if member_info.mobile else '')
        sheet.merge_range(row, 10, row, 11, member_info.enter_times)
        if member_info.is_final_passed == 1:
            sheet.merge_range(row, 12, row, 13, '已通关')
        else:
            sheet.merge_range(row, 12, row, 13, str(member_info.check_point_index))
        sheet.merge_range(row, 14, row, 15, member_info.first_time_login.strftime("%Y-%m-%d"))
        sheet.merge_range(row, 16, row, 17, member_info.draw_red_packet_count)
        sheet.merge_range(row, 18, row, 19, member_info.draw_red_packet_amount)


def export_new_info(workbook, race_cid, s_daily_code='', e_daily_code=''):
    """
    新增信息
    :param workbook:
    :param race_cid:
    :param s_daily_code:
    :param e_daily_code:
    :return:
    """
    match = MatchStage({'race_cid': race_cid})
    if s_daily_code and e_daily_code:
        match['daily_code'] = {'$gte': s_daily_code, '$lte': e_daily_code}
    group = GroupStage({'daily_code': '$daily_code', 'race_cid': '$race_cid'},
                       enter_times={'$sum': '$enter_times'},
                       draw_red_packet_count={'$sum': '$draw_red_packet_count'},
                       draw_red_packet_amount={'$sum': '$draw_red_packet_amount'},
                       new_user_count={'$sum': '$is_new_user'}
                       )
    sort = SortStage([('_id.daily_code', ASC)])
    total_user_count = 0
    total_enter_times = 0
    total_draw_red_packet_count = 0
    total_draw_red_packet_amount = 0
    exported_member_list = MemberStatisticInfo.sync_aggregate([match, group, sort]).to_list(None)

    sheet = workbook.add_worksheet("新增信息")
    sheet.merge_range(0, 0, 0, 1, '日期')
    sheet.merge_range(0, 2, 0, 3, '新增会员数')
    sheet.merge_range(0, 4, 0, 5, '新增答题次数')
    sheet.merge_range(0, 6, 0, 7, '新增红包领取数')
    sheet.merge_range(0, 8, 0, 9, '新增红包领取金额')
    sheet.merge_range(0, 10, 0, 11, '总会员数')
    sheet.merge_range(0, 12, 0, 13, '总答题次数')
    sheet.merge_range(0, 14, 0, 15, '总红包领取数')
    sheet.merge_range(0, 16, 0, 17, '总红包领取金额')
    for index, info in enumerate(exported_member_list):
        row = index + 1
        sheet.merge_range(row, 0, row, 1, info.id.get('daily_code'))
        sheet.merge_range(row, 2, row, 3, info.new_user_count)
        sheet.merge_range(row, 4, row, 5, info.enter_times)
        sheet.merge_range(row, 6, row, 7, info.draw_red_packet_count)
        sheet.merge_range(row, 8, row, 9, info.draw_red_packet_amount)
        total_user_count += info.new_user_count
        total_enter_times += info.enter_times
        total_draw_red_packet_count += info.draw_red_packet_count
        total_draw_red_packet_amount += info.draw_red_packet_amount
        sheet.merge_range(row, 10, row, 11, total_user_count)
        sheet.merge_range(row, 12, row, 13, total_enter_times)
        sheet.merge_range(row, 14, row, 15, total_draw_red_packet_count)
        sheet.merge_range(row, 16, row, 17, total_draw_red_packet_amount)


def export_race(race_cid):
    today = datetime.datetime.now()
    today_code = format(today, "%Y-%m-%d")
    race = Race.sync_find_one({'cid': race_cid})
    title = '{}_会员信息_{}.xlsx'.format(race.title, today_code)
    workbook = xlsxwriter.Workbook(title)
    export_member_to_excel(workbook, race.cid)
    export_new_info(workbook, race.cid)
    workbook.close()
    return title


if __name__ == '__main__':
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D 扬州 DF1EDC30F120AEE93351A005DC97B5C1
    export_race("CA755167DEA9AA89650D11C10FAA5413")
    # export_race("3040737C97F7C7669B04BC39A660065D")
    # export_race("F742E0C7CA5F7E175844478D74484C29")
    # export_race("DF1EDC30F120AEE93351A005DC97B5C1")
