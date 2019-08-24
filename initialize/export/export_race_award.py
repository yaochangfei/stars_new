# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime

import xlsxwriter
from pymongo import ReadPreference


from commons.common_utils import str2datetime
from db.models import MemberCheckPointHistory, RaceGameCheckPoint, RedPacketBox, Race, BaseModel
from initialize.export.export_town_information import convert
from motorengine.fields import DateTimeField



class DailyAward(object):
    def __init__(self, daily_code, attend_count, lottery_count, win_count):
        self.daily_code = daily_code
        self.attend_count = attend_count
        self.lottery_count = lottery_count
        self.win_count = win_count
        self.win_rate = '0.00'
        if self.lottery_count:
            self.win_rate = '%.2f' % (win_count / lottery_count)

    def __str__(self):
        return ','.join(['%s:%s' % item for item in self.__dict__.items()])


class StatisticAwardInfo(object):
    def __init__(self, daily_awards):
        self.attend_total_count = 0
        self.lottery_total_count = 0
        self.win_total_count = 0
        self.total_win_rate = '0.00'
        self.daily_awards = daily_awards
        for daily_award in daily_awards:
            self.attend_total_count += daily_award.attend_count
            self.lottery_total_count += daily_award.lottery_count
            self.win_total_count += daily_award.win_count
            if self.lottery_total_count:
                self.total_win_rate = '%.2f' % (self.win_total_count/self.lottery_total_count)

    def __str__(self):
        return ','.join(['%s:%s' % item for item in self.__dict__.items()])


class CheckPointAward(object):
    def __init__(self, check_point: RaceGameCheckPoint, award_static: StatisticAwardInfo):
        self.check_point = check_point
        self.award_static = award_static

    def __str__(self):
        return ','.join(['%s:%s' % item for item in self.__dict__.items()])


def get_date_range(start_date):
    """
    获取活动开始到至今的时间段
    :param start_date:
    :return:
    """
    date_list = []
    end_date = datetime.datetime.now()
    while start_date <= end_date:
        date_str = start_date.strftime("%Y%m%d")
        date_list.append(date_str)
        start_date += datetime.timedelta(days=1)
    return date_list


def statistic_award_of_race(race_cid, daily_codes):
    """
    该活动下每个关卡参与人数、抽奖人数、中奖人数记录
    :param race_cid:
    :return:
    """
    check_point_list = RaceGameCheckPoint.sync_find({"race_cid": race_cid}).to_list(None)
    result = []
    check_point_list.sort(key=lambda checkpoint: checkpoint.index)
    for check_point in check_point_list:
        print("统计", check_point.alias, check_point.cid)
        statistic_award_info = statistic_award_info_of_check_point(check_point.cid, daily_codes)
        result.append(CheckPointAward(check_point, statistic_award_info))
        print(statistic_award_info)
    # check_point_sort = sorted(check_point_list,key=lambda check_point: check_point.index)
    # check_point_alias = [x.alias for x in check_point_sort]
    # export_to_excel(result, check_point_alias)
    return result


def statistic_award_info_of_check_point(check_point_cid: str, daily_codes: list):
    """
    关卡的统计信息
    :param check_point_cid:
    :param daily_codes:
    :return:
    """
    daily_awards = []
    for daily_code in daily_codes:
        daily_award = statistic_daily_award_of_check_point(check_point_cid, daily_code)
        daily_awards.append(daily_award)
    return StatisticAwardInfo(daily_awards)


def statistic_daily_award_of_check_point(check_point_cid: str, daily_code):
    """
    统计每一关每天参与人数、抽奖人数、中奖人数
    :param check_point_cid: 关卡cid
    :return:
    """
    # print("正在统计关卡:", check_point.alias, check_point.cid)
    match = {'check_point_cid': check_point_cid, 'record_flag': 1}
    red_match = {'checkpoint_cid': check_point_cid}
    s_date = str2datetime(daily_code, date_format='%Y%m%d').replace(hour=0, minute=0, second=0)
    e_date = s_date + datetime.timedelta(days=1)
    match['fight_datetime'] = {'$gte': s_date, '$lt': e_date}
    red_match['draw_dt'] = {'$gte': s_date, '$lt': e_date}
    # 参与人数
    attend_member = MemberCheckPointHistory.sync_distinct("member_cid", match)
    attend_count = len(attend_member)
    # 当前关卡的红包
    current_checkpoint_reds = RedPacketBox.sync_find(red_match, read_preference=ReadPreference.PRIMARY).batch_size(2000)
    lottery_count = 0
    win_count = 0
    for current_checkpoint_red in current_checkpoint_reds:
        lottery_count += 1
        if current_checkpoint_red.award_cid:
            win_count += 1
    daily_award = DailyAward(daily_code, attend_count, lottery_count, win_count)
    # print(check_point_cid, daily_award)
    return daily_award


def export_to_excel(race_cid):
    """
    excel导出
    :param race_cid:
    :return:
    """
    race = Race.sync_find_one({"cid": race_cid})
    daily_codes = get_date_range(race.start_datetime)
    race_awards = statistic_award_of_race(race_cid, daily_codes)
    daily_code = format(datetime.datetime.now(),'%Y%m%d')
    workbook = xlsxwriter.Workbook('{}关卡红包情况_{}.xlsx'.format(race.title,daily_code))
    sheet = workbook.add_worksheet(race.title)
    # excel行名
    second_row_num = 4
    sheet.merge_range(0, 0, 1, 0, '关卡名')
    for index, daily_code in enumerate(daily_codes):
        start_col_index = index * second_row_num + 1
        sheet.merge_range(0, start_col_index, 0, start_col_index + second_row_num - 1, daily_code)
        sheet.write_string(1, start_col_index, '参与人次')
        sheet.write_string(1, start_col_index + 1, '抽奖人数')
        sheet.write_string(1, start_col_index + 2, '中奖人数')
        sheet.write_string(1, start_col_index + 3, '中奖率')
        if index == len(daily_codes) - 1:
            total_col_index = start_col_index + 3
            sheet.merge_range(0, total_col_index, 0, total_col_index + second_row_num - 1, "总计")
            sheet.write_string(1, total_col_index, '参与人次')
            sheet.write_string(1, total_col_index + 1, '抽奖人数')
            sheet.write_string(1, total_col_index + 2, '中奖人数')
            sheet.write_string(1, start_col_index + 3, '中奖率')

    for row_index, check_point_award in enumerate(race_awards):
        name = check_point_award.check_point.alias
        daily_awards = check_point_award.award_static.daily_awards
        row_num = row_index + 2
        sheet.write_string(row_num, 0, name)
        if daily_awards and len(daily_awards) > 0:
            for col_index, daily_award in enumerate(daily_awards):
                col_num = col_index * second_row_num + 1
                sheet.write_number(row_num, col_num, daily_award.attend_count)
                sheet.write_number(row_num, col_num + 1, daily_award.lottery_count)
                sheet.write_number(row_num, col_num + 2, daily_award.win_count)
                sheet.write_string(row_num, col_num + 3, daily_award.win_rate)
                if col_index == len(daily_awards) - 1:
                    sheet.write_number(row_num, col_num + 3, check_point_award.award_static.attend_total_count)
                    sheet.write_number(row_num, col_num + 4, check_point_award.award_static.lottery_total_count)
                    sheet.write_number(row_num, col_num + 5, check_point_award.award_static.win_total_count)
                    sheet.write_string(row_num, col_num + 6, check_point_award.award_static.total_win_rate)
    _last_row = len(race_awards) + 2
    _last_col = (len(daily_codes) + 1) * 3
    sheet.write_string(_last_row, 0, '总计')
    for i in range(1, _last_col + 1):
        col_name = convert(i)
        formula = "=SUM({}{}:{}{})".format(col_name, 3, col_name, _last_row)
        sheet.write_formula(_last_row, i, formula)

    workbook.close()

class Test(BaseModel):
    s_date = DateTimeField(default=datetime.datetime.now())
    e_date = DateTimeField(default=datetime.datetime.now())

if __name__ == '__main__':
    # 安徽活动
    # export_to_excel('3040737C97F7C7669B04BC39A660065D')
    # 六安活动
    export_to_excel('CA755167DEA9AA89650D11C10FAA5413')
    # statistic_daily_award_of_check_point("54B20BEDA100A9925E2E86347F42F0D2",'20190520')

