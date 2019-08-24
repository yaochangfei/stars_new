import datetime

import xlsxwriter

from db.models import RaceMapping, Member, AdministrativeDivision, Race, ReportRacePeopleStatistics
from motorengine import ASC
from motorengine.stages import LookupStage, MatchStage, ProjectStage, GroupStage, SortStage
from tasks.utils import get_region_match


def write_sheet_race_member_information(race_cid: str, post_code):
    """
    导出该活动下面得会员信息，主要是手机号码
    :param race_cid:
    :param post_code
    :return: excel
    """
    workbook = xlsxwriter.Workbook('黄山市会员信息统计.xlsx')
    sheet = workbook.add_worksheet('黄山市会员信息')
    sheet.merge_range(0, 0, 0, 1, '昵称')
    sheet.write_string(0, 2, '地区')
    sheet.merge_range(0, 3, 0, 4, '手机号码')
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    district_lookup_stage = LookupStage(AdministrativeDivision, 'district_code', 'post_code', 'district_list')
    match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1, 'city_code': post_code})
    #  该市下面所有得区
    district_title_list = AdministrativeDivision.sync_distinct('title', {'parent_code': post_code})
    race_mapping_cursor = RaceMapping.sync_aggregate([match_stage, lookup_stage, district_lookup_stage])
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
    num = 1
    while True:
        try:
            race_mapping = race_mapping_cursor.next()
            if race_mapping:
                if race_mapping.member_list and race_mapping.district_list:
                    member = race_mapping.member_list[0]
                    district = race_mapping.district_list[0]
                    if district.title in district_title_list:
                        sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                        sheet.write_string(num, 2, district.title, data_center_format)
                        sheet.merge_range(num, 3, num, 4, str(race_mapping.mobile), data_center_format)
                        num += 1
            else:
                continue
        except StopIteration:
            break
    workbook.close()


def export_race_data(workbook, race_cid: str, sheet_name):
    """
    导出每日参与人数，每日新增人数，每日新增人次
    :param race_cid:
    :return:
    """
    # yesterday_time = get_yesterday()
    # time_match = MatchStage({'updated_dt': {'$lt': yesterday_time}})
    race = Race.sync_get_by_cid(race_cid)

    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})

    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})

    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    match = {'race_cid': race_cid, 'auth_address.province': {'$ne': None}, 'auth_address.city': {"$in": city_name_list},
             'auth_address.district': {"$in": dist_list}}
    sheet = workbook.add_worksheet(sheet_name)
    cursor = RaceMapping.sync_aggregate(
            [MatchStage(match),
             ProjectStage(**{
                 'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
                 'auth_address': "$auth_address",
                 'member_cid': "$member_cid"
             }),
             GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'}, sum={'$sum': 1},
                        auth_address={'$first': '$auth_address'}),
             SortStage([('_id.daily_code', ASC)])])
    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')

    daily_list = []
    prize_list = []
    county_map = {}

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('district')
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)

                city = data.auth_address.get('city')
                if not city:
                    continue
                sheet.write_string(_current_row, 0, city)
                ad_city = AdministrativeDivision.sync_find_one({'title': city})
                _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
                for _c in _county:
                    county_map[_c] = city

                sheet.write_string(_current_row, 1, title)

            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list) + 1
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 2

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in prize_list:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet(book, race_cid, sheet_name, pre_match={}, count_type='$people_num'):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :param count_type:
    :return:
    """

    race = Race.sync_get_by_cid(race_cid)

    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})

    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})

    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    match = {'race_cid': race_cid, 'province': {'$ne': None}, 'city': {"$in": city_name_list},
             'district': {"$in": dist_list}}
    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'district': '$district'}, sum={'$sum': count_type},
                             city={'$first': '$city'})
    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 2, daily_code)
        daily_map[daily_code] = index + 2

    district_list = ReportRacePeopleStatistics.sync_distinct('district', match)
    district_map = {}
    for index, district in enumerate(district_list):
        sheet.write_string(index + 1, 1, district if district else '其他')
        district_map[district if district else '其他'] = index + 1

    cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(match), group_stage])

    county_map = dict()
    v_list = list()
    _max_row = 0
    while True:
        try:
            stat = cursor.next()

            city = stat.city if stat.city else '其他'
            district = stat.id.get('district')
            daily_code = stat.id.get('daily_code')

            _row = district_map.get(district if district else '其他')
            sheet.write_string(_row, 0, city)
            ad_city = AdministrativeDivision.sync_find_one({'title': city})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
            for _c in _county:
                county_map[_c] = city

            sheet.write_number(_row, daily_map.get(daily_code), stat.sum)

            if _row > _max_row:
                _max_row = _row

            v_list.append(stat.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in district_map:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_enter_data(book, race_cid, sheet_name, pre_match={}, count_type='$people_num'):
    """
    总共参与人数/人次
    :param book:
    :param sheet_name:
    :param race_cid
    :param pre_match:
    :param count_type:
    :return:
    """

    match = {'race_cid': race_cid}
    if pre_match:
        match.update(pre_match)

    race = Race.sync_get_by_cid(race_cid)
    match.update(get_region_match(race))

    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'district': '$district'}, sum={'$sum': count_type},
                             city={'$first': '$city'})
    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 2, daily_code)
        daily_map[daily_code] = index + 2

    district_list = ReportRacePeopleStatistics.sync_distinct('district', match)
    district_map = {}
    for index, district in enumerate(district_list):
        sheet.write_string(index + 1, 1, district if district else '其他')
        district_map[district if district else '其他'] = index + 1

    cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(match), group_stage])

    county_map = dict()
    v_list = list()
    _max_row = 0
    while True:
        try:
            stat = cursor.next()

            city = stat.city if stat.city else '其他'
            district = stat.id.get('district')
            daily_code = stat.id.get('daily_code')

            _row = district_map.get(district if district else '其他')
            sheet.write_string(_row, 0, city)
            ad_city = AdministrativeDivision.sync_find_one({'title': city})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
            for _c in _county:
                county_map[_c] = city

            sheet.write_number(_row, daily_map.get(daily_code), stat.sum)

            if _row > _max_row:
                _max_row = _row

            v_list.append(stat.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in district_map:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_daily_increase_people(book, race_cid, sheet_name='每日新增参与人数', pre_match={}):
    """
    每日新增人数
    :param book:
    :param sheet_name:
    :param race_cid
    :param pre_match:
    :return:
    """
    race = Race.sync_get_by_cid(race_cid)

    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})

    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})

    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    match = {'race_cid': race_cid, 'record_flag': 1, 'auth_address.province': {'$ne': None}, 'auth_address.city': {"$in": city_name_list},
             'auth_address.district': {"$in": dist_list}}
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'auth_address': "$auth_address",
             "member_list": "$member_list"
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'}, sum={'$sum': 1},
                    auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])])

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')

    daily_list = []
    prize_list = []
    county_map = {}

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('district')
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)

                city = data.auth_address.get('city')
                if not city:
                    continue
                sheet.write_string(_current_row, 0, city)
                ad_city = AdministrativeDivision.sync_find_one({'title': city})
                _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
                for _c in _county:
                    county_map[_c] = city

                sheet.write_string(_current_row, 1, title)

            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list) + 1
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 2

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in prize_list:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))



if __name__ == '__main__':
    print('start -------------------')
    workbook = xlsxwriter.Workbook('安徽活动统计.xlsx')
    now = datetime.datetime.now()
    race_cid = "3040737C97F7C7669B04BC39A660065D"
    # write_sheet_race_member_information('3040737C97F7C7669B04BC39A660065D', '341000')
    # write_sheet(workbook, "3040737C97F7C7669B04BC39A660065D",'每日参与人数', pre_match={'updated_dt': {'$lte': now}})
    # export_race_data(workbook, "3040737C97F7C7669B04BC39A660065D", '每日新增人数')
    # # write_sheet_daily_incre_people(workbook, '每日新增参与人数', pre_match={'updated_dt': {'$lte': now}})
    # write_sheet(workbook, "3040737C97F7C7669B04BC39A660065D",'每日参与人次', pre_match={'updated_dt': {'$lte': now}}, count_type='$total_num')
    # write_sheet(workbook, "F742E0C7CA5F7E175844478D74484C29",'每日通关人数', pre_match={'updated_dt': {'$lte': now}}, count_type='$pass_num')
    write_sheet_enter_data(workbook, race_cid, '每日参与人数', pre_match={'updated_dt': {'$lte': now}})
    write_sheet_daily_increase_people(workbook, race_cid, '每日新增参与人数', pre_match={'updated_dt': {'$lte': now}})
    write_sheet_enter_data(workbook, race_cid, '每日参与人次', pre_match={'updated_dt': {'$lte': now}},
                           count_type='$total_num')
    workbook.close()
    print('end ------------------------------')


