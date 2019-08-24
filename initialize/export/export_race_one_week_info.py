#   导入该活动的累计参与人数，参与人次，新增人数，新增人次，通关人数，红包领取情况
import copy
import datetime
import os

import xlsxwriter

from commons.common_utils import datetime2str
from db.models import Race, AdministrativeDivision, RaceMemberEnterInfoStatistic
from motorengine import ASC
from motorengine.stages import MatchStage, ProjectStage, GroupStage, SortStage
from settings import SITE_ROOT

today = format(datetime.datetime.now(), "%Y-%m-%d%H:%M")


def export_race_enter_position(race_cid: str, title, n):
    """
    导出活动下面参与情况
    :return:
    """
    if not isinstance(race_cid, str):
        raise ValueError("race_cid is not str")
    current = datetime.datetime.now()
    export_time_list = [(current + datetime.timedelta(days=-n)).replace(hour=0, minute=0, second=0) for n in (range(1, n))]
    export_time_list.sort()
    export_time = [transform_time_format(export_dt) for export_dt in export_time_list]
    export_time.sort()
    workbook = xlsxwriter.Workbook("{title}{today}.xlsx".format(title=title, today=today))
    excel_name = "{title}{today}.xlsx".format(title=title, today=today)
    head_list = ["新增人数", "参与人数", "参与次数", "通关人数", "红包发放数", "红包领取数量", "红包发放金额", "红包领取金额"]
    sheet = workbook.add_worksheet("{title}一周数据".format(title=title))
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei'})
    sheet.merge_range(0, 0, 1, 0, "城市", data_center_format)
    sheet.merge_range(0, 1, 1, 1, "区县", data_center_format)
    sheet.write_string(1, 2, "累计人数")
    sheet.write_string(1, 3, "累计参与次数")
    sheet.write_string(1, 4, "累计红包发放总数")
    #  excel填充一周日期
    for i in range(1, n):
        sheet.merge_range(0, 7 * (i - 1) + 5 + i - 1, 0, 7 * (i - 1) + 5 + i - 1 + 7, export_time[i - 1], data_center_format)
        for head in range(7 * (i - 1) + 5 + i - 1, 7 * (i - 1) + 5 + i - 1 + 7 + 1):
            index = head - 8 * (i - 1) - 5
            sheet.write_string(1, head, head_list[index])
    prov_match = MatchStage({'province': {'$ne': None}})
    race = Race.sync_get_by_cid(race_cid)
    #  市级活动，如六安市，扬州市
    if race.city_code:
        city_code_list = AdministrativeDivision.sync_distinct('code', {'code': race.city_code})
        #  该活动的所属城市范围
        city_name_list = AdministrativeDivision.sync_distinct('title', {'code': race.city_code})
    else:
        prov = AdministrativeDivision.sync_find_one({'code': race.province_code})
        city_code_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
        city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
        prov_match = MatchStage({'province': prov.title})
    dist_list = []
    for city_code in city_code_list:
        #  该活动区县的范围
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city_code})
    address_sort = SortStage([('_id.city', ASC), ('_id.district', ASC)])
    match = {"race_cid": race_cid, 'record_flag': 1, 'city': {'$in': city_name_list}, 'district': {'$in': dist_list}}
    address_list = RaceMemberEnterInfoStatistic.sync_aggregate(
        [
            MatchStage(match),
            prov_match,
            ProjectStage(**{
                'province': "$province",
                "city": "$city",
                "district": "$district"
            }),
            GroupStage(
                {'district': '$district', 'city': '$city'}, sum={'$sum': 1}),
            address_sort
        ]
    )
    #   拿到该活动下的所有区县和城市对应字典表
    dis_map = get_race_district_mapping(sheet, address_list)
    # 时间与地区人数的字典 {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    quantity_time_dict = {}
    #  每日参与人数一周的数据  时间与地区人数的字典  {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    enter_quantity_time_dict = {}
    #  时间与地区次数的字典 {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    count_time_dict = {}
    #  一周通关的人数   {'20190702': {'六安市-叶集区': 20, "六安市-舒城县": 15}, '20190703': {'六安市-舒城县': 30}}
    pass_quantity_time_dict = {}
    #  一周红包发放数量和金额的字典
    red_give_dict = {}
    red_give_amount_dict = {}
    #   一周红包领取数量和金额的字典
    red_receive_dict = {}
    red_receive_amount_dict = {}
    base_match = {'race_cid': race_cid, 'city': {'$in': city_name_list}, 'district': {'$in': dist_list},
                  'daily_code': {'$gte': export_time[0],
                                 '$lte':  transform_time_format((export_time_list[-1] + datetime.timedelta(days=1)))}}
    total_match = copy.deepcopy(base_match)
    del total_match['daily_code']
    total_district_count_dict = {}
    total_district_times_dict = {}
    total_send_red_packet_dict = {}
    race_total_info_cursor = RaceMemberEnterInfoStatistic.sync_aggregate([
        MatchStage(total_match),
        GroupStage(
            {'city': '$city', 'district': '$district'},
            count_sum={'$sum': '$increase_enter_count'}, enter_times_sum={'$sum': '$enter_times'},
            grant_red_packet_count={'$sum': "$grant_red_packet_count"},
        )
        ]
    )
    while True:
        try:
            data = race_total_info_cursor.next()
            district = data.id.get('district')
            if district not in total_district_count_dict:
                total_district_count_dict[district] = data.count_sum
            if district not in total_district_times_dict:
                total_district_times_dict[district] = data.enter_times_sum
            if district not in total_send_red_packet_dict:
                total_send_red_packet_dict[district] = data.grant_red_packet_count
        except StopIteration:
            break
        except Exception as e:
            raise e
    #  每日参与人数，总计
    for district, data in total_district_count_dict.items():
        _col = dis_map.get(district)
        sheet.write_number(_col, 2, data)
    #  每日参与次数，总计
    for district, data in total_district_times_dict.items():
        _col = dis_map.get(district)
        sheet.write_number(_col, 3, data)
    #  每日累计发放红包数量
    for district, data in total_send_red_packet_dict.items():
        _col = dis_map.get(district)
        sheet.write_number(_col, 4, data)
    race_member_info_list = RaceMemberEnterInfoStatistic.sync_aggregate(
        [
            MatchStage(base_match),
            GroupStage(
                {"daily_code": "$daily_code", 'district': '$district', 'city': '$city'},
                increase_quantity_sum={'$sum': '$increase_enter_count'}, enter_count_sum={'$sum': '$enter_count'},
                pass_count_sum={'$sum': '$pass_count'}, enter_times_sum={'$sum': '$enter_times'},
                grant_red_packet_count_sum={'$sum': '$grant_red_packet_count'},
                grant_red_packet_amount_sum={'$sum': '$grant_red_packet_amount'},
                draw_red_packet_count_sum={'$sum': '$draw_red_packet_count'},
                draw_red_packet_amount_sum={'$sum': '$draw_red_packet_amount'},
            ),
            address_sort
        ]
    )
    for race_member_info in race_member_info_list:
        daily = race_member_info.id.get('daily_code')
        city = race_member_info.id.get('city')
        district = race_member_info.id.get('district')
        if city and district:
            if daily not in quantity_time_dict:
                #  每日新增参与人数
                quantity_time_dict[daily] = {
                    "{city}-{district}".format(city=city, district=district): race_member_info.increase_quantity_sum}
            else:
                quantity_time_dict[daily].update(
                    {"{city}-{district}".format(city=city, district=district): race_member_info.increase_quantity_sum})
            if daily not in enter_quantity_time_dict:
                #  每日参与人数
                enter_quantity_time_dict[daily] = {
                    "{city}-{district}".format(city=city, district=district): race_member_info.enter_count_sum}
            else:
                enter_quantity_time_dict[daily].update(
                    {"{city}-{district}".format(city=city, district=district): race_member_info.enter_count_sum})
            if daily not in count_time_dict:
                #  每日参与次数
                count_time_dict[daily] = {
                    "{city}-{district}".format(city=city, district=district): race_member_info.enter_times_sum}
            else:
                count_time_dict[daily].update(
                    {"{city}-{district}".format(city=city, district=district): race_member_info.enter_times_sum})
            if daily not in pass_quantity_time_dict:
                #    每日通关人数
                pass_quantity_time_dict[daily] = {
                    "{city}-{district}".format(city=city, district=district): race_member_info.pass_count_sum}
            else:
                pass_quantity_time_dict[daily].update(
                    {"{city}-{district}".format(city=city, district=district): race_member_info.pass_count_sum})
            if daily not in red_give_dict:
                #  每日红包发放数量
                red_give_dict[daily] = {
                    "{city}-{district}".format(city=city,
                                               district=district): race_member_info.grant_red_packet_count_sum}
            else:
                red_give_dict[daily].update(
                    {"{city}-{district}".format(city=city,
                                                district=district): race_member_info.grant_red_packet_count_sum})
            if daily not in red_give_amount_dict:
                #  每日红包发放金额
                red_give_amount_dict[daily] = {
                    "{city}-{district}".format(city=city,
                                               district=district): race_member_info.grant_red_packet_amount_sum}
            else:
                red_give_amount_dict[daily].update(
                    {"{city}-{district}".format(city=city,
                                                district=district): race_member_info.grant_red_packet_amount_sum})
            if daily not in red_receive_dict:
                #  每日红包领取数量
                red_receive_dict[daily] = {
                    "{city}-{district}".format(city=city,
                                               district=district): race_member_info.draw_red_packet_count_sum}
            else:
                red_receive_dict[daily].update(
                    {"{city}-{district}".format(city=city,
                                                district=district): race_member_info.draw_red_packet_count_sum})
            if daily not in red_receive_amount_dict:
                #    每日红包领取金额
                red_receive_amount_dict[daily] = {
                    "{city}-{district}".format(city=city,
                                               district=district): race_member_info.draw_red_packet_amount_sum}
            else:
                red_receive_amount_dict[daily].update(
                    {"{city}-{district}".format(city=city,
                                                district=district): race_member_info.draw_red_packet_amount_sum})
        else:
            continue
    #  每日新增人数在excel的位置
    quantity_increase_position_list = [4 + 8 * (i - 1) for i in range(1, n)]
    #  每日参与人数在excel的位置
    quantity_enter_position_list = [5 + 8 * (i - 1) for i in range(1, n)]
    #   每日参与次数在excel的位置
    count_enter_position_list = [6 + 8 * (i - 1) for i in range(1, n)]
    #   每日通关次数在excel的位置
    pass_enter_position_list = [7 + 8 * (i - 1) for i in range(1, n)]
    #  红包发放数量在excel的位置
    red_give_position_list = [8 + 8 * (i - 1) for i in range(1, n)]
    #   红包发放金额在excel的位置
    red_give_amount_list = [10 + 8 * (i - 1) for i in range(1, n)]
    #  红包领取数量在excel的位置
    red_receive_position_list = [9 + 8 * (i - 1) for i in range(1, n)]
    #  红包领取金额在excel的位置
    red_receive_amount_list = [11 + 8 * (i - 1) for i in range(1, n)]
    #  填充每日新增人数
    write_excel_data(sheet, quantity_time_dict, dis_map, export_time, quantity_increase_position_list, save=None)

    #  excel 填充每日参与人数
    write_excel_data(sheet, enter_quantity_time_dict, dis_map, export_time, quantity_enter_position_list, save=None)
    #  excel 填充每日参与次数
    write_excel_data(sheet, count_time_dict, dis_map, export_time, count_enter_position_list, save=None)
    #  excel 填充每日通关人数
    write_excel_data(sheet, pass_quantity_time_dict, dis_map, export_time, pass_enter_position_list, save=None)
    #  excel 填充每日发放个数
    write_excel_data(sheet, red_give_dict, dis_map, export_time, red_give_position_list, save=None)
    #  excel 填充每日领取金额
    write_excel_data(sheet, red_give_amount_dict, dis_map, export_time, red_give_amount_list, save=2)
    #  excel 填充每日领取个数
    write_excel_data(sheet, red_receive_dict, dis_map, export_time, red_receive_position_list, save=None)
    #  excel 填充每日领取金额
    write_excel_data(sheet, red_receive_amount_dict, dis_map, export_time, red_receive_amount_list, save=2)
    workbook.close()
    return excel_name

def transform_time_format(export_dt):
    """
    把时间日期格式得数据转换成指定得字符串形式
    :param export_dt:
    :return:
    """
    time_str = datetime2str(export_dt, date_format='%Y%m%d')
    return time_str


def write_excel_data(sheet, data_dict, dis_map, export_time, data_list, save=None):
    """
    写入excel
    :param sheet:
    :param data_dict:
    :param dis_map:
    :param export_time:
    :param data_list:
    :param save:
    :return:
    """
    for k, v_dict in data_dict.items():
        time_index = export_time.index(k)
        _col = data_list[time_index]
        for dis, data in v_dict.items():
            district_index = dis_map.get(dis.split("-")[-1])
            if district_index:
                if not save:
                    sheet.write_number(district_index, _col, data)
                else:
                    sheet.write_number(district_index, _col, round(data, 2))


def get_race_district_mapping(sheet, address_list):
    """
    得到该活动下的区域和城市的映射表
    :param address_list:
    :param sheet
    :return:
    """
    dis_map = {}
    for index, address in enumerate(address_list):
        sheet.write_string(index + 2, 0, address.id.get('city'))
        sheet.write_string(index + 2, 1, address.id.get('district'))
        if address.id.get('district') not in dis_map:
            dis_map[address.id.get('district')] = index + 2
        else:
            dis_map[address.id.get('district')] += index + 2
    return dis_map


def export_race_one_week_excel():
    excel_title_list = []
    race_dict = {"CA755167DEA9AA89650D11C10FAA5413": "六安市", "3040737C97F7C7669B04BC39A660065D": "安徽省",
                 "F742E0C7CA5F7E175844478D74484C29": "贵州省", "DF1EDC30F120AEE93351A005DC97B5C1": "扬州市"}
    race_list = Race.sync_find({'status': 1})
    for race in race_list:
        cid = race.cid
        title = race.title
        if race.cid == '160631F26D00F7A2DC56DAE2A0C4AF12':
            continue
        excel_name = export_race_enter_position(cid, '{title}一周数据'.format(title=title), 8)
        excel_title_list.append(os.path.join(SITE_ROOT, excel_name))
    return excel_title_list


if __name__ == '__main__':
    # export_race_one_week_excel()
    race_dict = {"F742E0C7CA5F7E175844478D74484C29": "贵州省"}
    for cid, title in race_dict.items():
        export_race_enter_position(cid, '{title}一周数据.xlsx'.format(title=title), 8)
    # export_race_enter_position("CA755167DEA9AA89650D11C10FAA5413", "六安市", 29)
    # export_race_enter_position("3040737C97F7C7669B04BC39A660065D", "安徽省", 68)
    # export_race_enter_position("F742E0C7CA5F7E175844478D74484C29", "贵州省", 121)
    # export_race_enter_position("DF1EDC30F120AEE93351A005DC97B5C1", "扬州市", 174)