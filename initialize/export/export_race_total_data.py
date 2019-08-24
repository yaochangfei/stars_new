#   导入该活动的累计参与人数，参与人次，新增人数，新增人次，通关人数，红包领取情况
import datetime

import xlsxwriter

from commons.common_utils import datetime2str
from db.models import Race, AdministrativeDivision, Member, RaceMapping, ReportRacePeopleStatistics, RedPacketBox, \
    MemberCheckPointHistory
from initialize.export.export_race_people_information import get_export_param
from motorengine import ASC
from motorengine.stages import MatchStage, LookupStage, ProjectStage, GroupStage, SortStage

today = format(datetime.datetime.now(), "%Y-%m-%d%H:%M")


def export_race_enter_position(race_cid: str, title):
    """
    导出活动下面参与情况
    :return:
    """
    if not isinstance(race_cid, str):
        raise ValueError("race_cid is not str")
    now = datetime.datetime.now()
    export_time_list = [now + datetime.timedelta(days=-n) for n in (range(1, 8))]
    export_time_list.sort()
    export_time = [transform_time_format(export_dt) for export_dt in export_time_list]
    export_time.sort()
    workbook = xlsxwriter.Workbook(title + today + ".xlsx")
    head_list = ["新增人数", "参与人数", "参与次数", "通关人数", "红包发放数", "红包领取数量", "红包发放金额","红包领取金额"]
    sheet = workbook.add_worksheet(title + "一周数据")
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei'})
    sheet.merge_range(0, 0, 1, 0, "城市", data_center_format)
    sheet.merge_range(0, 1, 1, 1, "区县", data_center_format)
    sheet.write_string(1, 2, "累计人数")
    sheet.write_string(1, 3, "累计参与次数")
    for i in range(1, 8):
        sheet.merge_range(0, 7 * (i - 1) + 4 + i - 1, 0, 7 * (i - 1) + 4 + i - 1 + 7, export_time[i - 1], data_center_format)
        for head in range(7 * (i - 1) + 4 + i - 1, 7 * (i - 1) + 4 + i - 1 + 7 + 1):
            index = head - 8 * (i - 1) - 4
            sheet.write_string(1, head, head_list[index])
    midnight = (datetime.datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    race = Race.sync_get_by_cid(race_cid)
    #  市级活动，如六安市，扬州市
    if race.city_code:
        city_code_list = AdministrativeDivision.sync_distinct('code', {'code': race.city_code})
        #  该活动的所属城市范围
        city_name_list = AdministrativeDivision.sync_distinct('title', {'code': race.city_code})
    else:
        city_code_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
        city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
    dist_list = []
    for city_code in city_code_list:
        #  该活动区县的范围
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city_code})
    #  最基本的人数match
    base_quantity_match = {'race_cid': race_cid, 'auth_address.province': {'$ne': None}, "record_flag": 1,
                           'auth_address.city': {"$in": city_name_list},
                           'auth_address.district': {"$in": dist_list}}
    #  最基本的次数match
    base_count_match = {'race_cid': race_cid, 'province': {'$ne': None}, "record_$pushflag": 1,
                           'city': {"$in": city_name_list},
                           'district': {"$in": dist_list}}
    #  最基本的参与人数match
    base_enter_quantity_match = {'race_cid': race_cid, 'auth_address.province': {'$ne': None}, "record_flag": 1,
                           'auth_address.city': {"$in": city_name_list},
                           'auth_address.district': {"$in": dist_list}}
    #  累计人数
    quantity_match_stage = MatchStage(
        {'race_cid': race_cid, 'auth_address.province': {'$ne': None}, "record_flag": 1,
         'auth_address.city': {"$in": city_name_list},
         'auth_address.district': {"$in": dist_list},
         'created_dt': {'$lte': midnight}})
    #  累计次数
    daily_code = datetime2str(datetime.datetime.now(), date_format='%Y%m%d')
    count_match = {'race_cid': race_cid, 'province': {'$ne': None}, 'city': {'$in': city_name_list},
                   'district': {'$in': dist_list}, 'daily_code': {'$lt': daily_code}}
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    address_sort = SortStage([('_id.city', ASC), ('_id.district', ASC)])
    quantity_list = RaceMapping.sync_aggregate(
        [
            quantity_match_stage,
            lookup_stage,
            ProjectStage(**{
                'auth_address': "$auth_address",
                "member_list": "$member_list"
            }), MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {'district': '$auth_address.district', 'city': '$auth_address.city'}, sum={'$sum': 1}),
            address_sort
        ]
    )
    count_list = ReportRacePeopleStatistics.sync_aggregate([
                    MatchStage(count_match),
                    GroupStage({'city': '$city', 'district': '$district'}, sum={'$sum': "$total_num"})
                ])
    dis_map = {}
    quantity = 0
    for index, address in enumerate(quantity_list):
        quantity += address.sum
        sheet.write_string(index + 2, 0, address.id.get('city'))
        sheet.write_string(index + 2, 1, address.id.get('district'))
        sheet.write_number(index + 2, 2, address.sum)
        if address.id.get('district') not in dis_map:
            dis_map[address.id.get('district')] = index + 2
        else:
            dis_map[address.id.get('district')] += index + 2
    count_map = {}
    for count in count_list:
        district = count.id.get('district')
        if district not in count_map:
            count_map[district] = count.sum
    print(count_map, 'count')
    print(dis_map, 'dis_map')
    for k, v in count_map.items():
        position = dis_map.get(k)
        if position:
            sheet.write_number(position, 3, v)
        #  有答题次数，没有人数的情况，跳过
        else:
            continue
    # 时间与地区人数的字典 {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    quantity_time_dict = {}
    #   一个星期的人数的数据
    base_quantity_match['created_dt'] = {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                         '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}
    one_week_quantity_list = RaceMapping.sync_aggregate(
        [
            MatchStage(base_quantity_match),
            lookup_stage,
            ProjectStage(**{
                'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
                'auth_address': "$auth_address",
                "member_list": "$member_list"
            }), MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {"daily_code": "$daily_code", 'district': '$auth_address.district', 'city': '$auth_address.city'}, sum={'$sum': 1}),
            address_sort
        ]
    )
    for quantity_data in one_week_quantity_list:
        daily = quantity_data.id.get('daily_code')
        city = quantity_data.id.get('city')
        district = quantity_data.id.get('district')
        if city and district:
            if daily not in quantity_time_dict:
                temp_dict = {}
                temp_dict["{city}-{district}".format(city=city, district=district)] = quantity_data.sum
                quantity_time_dict[daily] = temp_dict
            else:
                quantity_time_dict[daily].update({"{city}-{district}".format(city=city, district=district): quantity_data.sum})
        else:
            continue

    #  每日参与人数一周的数据
    #  时间与地区人数的字典  {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    base_enter_quantity_match['updated_dt'] = {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                               '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}
    enter_quantity_time_dict = {}
    one_week_enter_quantity_list = RaceMapping.sync_aggregate(
        [
            MatchStage(base_enter_quantity_match),
            lookup_stage,
            ProjectStage(**{
                'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$updated_dt"}},
                'auth_address': "$auth_address",
                "member_list": "$member_list"
            }), MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {"daily_code": "$daily_code", 'district': '$auth_address.district', 'city': '$auth_address.city'}, sum={'$sum': 1}),
            address_sort
        ]
    )

    for quantity_data in one_week_enter_quantity_list:
        daily = quantity_data.id.get('daily_code')
        city = quantity_data.id.get('city')
        district = quantity_data.id.get('district')
        if city and district:
            if daily not in enter_quantity_time_dict:
                temp_dict = {}
                temp_dict["{city}-{district}".format(city=city, district=district)] = quantity_data.sum
                enter_quantity_time_dict[daily] = temp_dict
            else:
                enter_quantity_time_dict[daily].update({"{city}-{district}".format(city=city, district=district): quantity_data.sum})
        else:
            continue
    # print(enter_quantity_time_dict, 'enter_quantity')
    #  每日新增参与次数一周的数据
    base_count_match['created_dt'] = {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                      '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}
    one_week_count_list = ReportRacePeopleStatistics.sync_aggregate([
                    MatchStage(base_count_match),
                    GroupStage({'city': '$city', 'district': '$district', 'daily_code': '$daily_code'}, sum={'$sum': "$total_num"})
                ])
    #  时间与地区次数的字典 {'20190702': {'六安市-叶集区': 20}, '20190703': {'六安市-舒城县': 30}}
    count_time_dict = {}
    for quantity_data in one_week_count_list:
        daily = quantity_data.id.get('daily_code')
        city = quantity_data.id.get('city')
        district = quantity_data.id.get('district')
        if city and district:
            if daily not in count_time_dict:
                temp_dict = {}
                temp_dict["{city}-{district}".format(city=city, district=district)] = quantity_data.sum
                count_time_dict[daily] = temp_dict
            else:
                count_time_dict[daily].update({"{city}-{district}".format(city=city, district=district): quantity_data.sum})
        else:
            continue

    #  一周通关的人数
    #  {'20190702': {'六安市-叶集区': 20, "六安市-舒城县": 15}, '20190703': {'六安市-舒城县': 30}}
    pass_quantity_time_dict = {}
    last_checkpoint_cid, _, _, _ = get_export_param(race_cid)   # 拿到最后一关的cid
    pass_match_stage = MatchStage({'check_point_cid': last_checkpoint_cid, 'status': 1, 'record_flag': 1,
                                   'created_dt': {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                                  '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}})
    check_point_cursor = MemberCheckPointHistory.sync_aggregate([pass_match_stage, lookup_stage])
    member_cid_list = []
    while True:
        try:
            check_point = check_point_cursor.next()
            if check_point.member_list:
                member = check_point.member_list[0]
                race_mapping = RaceMapping.sync_find_one(
                    {'race_cid': race_cid, 'member_cid': member.cid})
                if race_mapping:
                    if race_mapping.auth_address and race_mapping.auth_address.get('province'):
                        if check_point.member_cid not in member_cid_list:
                            district = race_mapping.auth_address.get('district')
                            city = race_mapping.auth_address.get('city')
                            if district and city:
                                member_cid_list.append(check_point.member_cid)
                                created_time = format(check_point.created_dt, "%Y%m%d")
                                if created_time not in pass_quantity_time_dict:
                                    pass_quantity_time_dict[created_time] = {"{city}-{district}".format(city=city, district=district): 1}
                                else:
                                    city_district = "{city}-{district}".format(city=city, district=district)
                                    v_dict = pass_quantity_time_dict.get(created_time)
                                    if city_district in v_dict:
                                        v_dict[city_district] += 1
                                    else:
                                        v_dict[city_district] = 1
                            else:
                                continue
        except StopIteration:
            break
        except Exception as e:
            raise e

    #  每日新增人数在excel的位置
    quantity_increase_position_list = [4 + 8 * (i - 1) for i in range(1, 8)]
    #  每日参与人数在excel的位置
    quantity_enter_position_list = [5 + 8 * (i - 1) for i in range(1, 8)]
    #   每日参与次数在excel的位置
    count_enter_position_list = [6 + 8 * (i - 1) for i in range(1, 8)]
    #   每日通关次数在excel的位置
    pass_enter_position_list = [7 + 8 * (i - 1) for i in range(1, 8)]
    #  红包发放数量在excel的位置
    red_give_position_list = [8 + 8 * (i - 1) for i in range(1, 8)]
    #   红包发放金额在excel的位置
    red_give_amount_list = [10 + 8 * (i - 1) for i in range(1, 8)]
    #  红包领取数量在excel的位置
    red_receive_position_list = [9 + 8 * (i - 1) for i in range(1, 8)]
    #  红包领取金额在excel的位置
    red_receive_amount_list = [11 + 8 * (i - 1) for i in range(1, 8)]
    print(quantity_increase_position_list)
    print(dis_map, 'dis_map6')
    print(quantity, 'quan')
    print(quantity_time_dict, 'quantity_time')
    #  填充每日新增人数
    write_excel_data(sheet, quantity_time_dict, dis_map, export_time, quantity_increase_position_list, save=None)

    #  excel 填充每日参与人数
    write_excel_data(sheet, enter_quantity_time_dict, dis_map, export_time, quantity_enter_position_list, save=None)

    #  excel 填充每日参与次数
    write_excel_data(sheet, count_time_dict, dis_map, export_time, count_enter_position_list, save=None)

    #  excel 填充每日通关人数
    write_excel_data(sheet, pass_quantity_time_dict, dis_map, export_time, pass_enter_position_list, save=None)
    red_give_dict = {}
    red_give_amount_dict = {}
    #   红包发放个数
    red_give_out_match = {"race_cid": race_cid, 'record_flag': 1, "award_cid": {'$ne': None}, 'member_cid': {'$ne': None},
                          'draw_dt': {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                         '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}}
    red_give_out_cursor = RedPacketBox.sync_aggregate(
        [
            MatchStage(red_give_out_match),
            lookup_stage,
            ProjectStage(**{
                'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$draw_dt"}},
                "member_cid": '$member_cid',
                "member_list": "$member_list",
                "award_amount": '$award_amount',
            }),
            MatchStage({'member_list': {'$ne': []}}),
            GroupStage({"daily_code": "$daily_code"}, amount_list={'$push': '$award_amount'}, cid_list={'$push': '$member_cid'}, sum={'$sum': 1})
        ]
    )
    while True:
        try:
            red_packet = red_give_out_cursor.next()
            if red_packet and red_packet.cid_list:
                cid_list = red_packet.cid_list
                amount_list = red_packet.amount_list
                print(len(amount_list), 'len_m')
                print(len(cid_list), 'len')

                daily = red_packet.id.get('daily_code')
                for cid, amount in zip(cid_list, amount_list):
                    race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': cid, 'auth_address.city': {'$in': city_name_list}, 'auth_address.district': {'$in': dist_list}})
                    if race_mapping:
                        city = race_mapping.auth_address.get('city')
                        district = race_mapping.auth_address.get('district')
                        city_district = "{city}-{district}".format(city=city, district=district)
                        if daily not in red_give_dict:
                            red_give_dict[daily] = {city_district: 1}
                        else:
                            v_dict = red_give_dict.get(daily)
                            if city_district not in v_dict:
                                v_dict[city_district] = 1
                            else:
                                v_dict[city_district] += 1
                        if daily not in red_give_amount_dict:
                            red_give_amount_dict[daily] = {city_district: amount}
                        else:
                            v_dict = red_give_amount_dict.get(daily)
                            if city_district not in v_dict:
                                v_dict[city_district] = amount
                            else:
                                v_dict[city_district] += amount

        except StopIteration:
            break
        except Exception as e:
            raise e
    print(red_give_dict, 'dict2')
    print(red_give_amount_dict, 'amount-dict2')
    #  excel 填充每日发放个数
    write_excel_data(sheet, red_give_dict, dis_map, export_time, red_give_position_list, save=None)
    #  excel 填充每日领取金额
    write_excel_data(sheet, red_give_amount_dict, dis_map, export_time, red_give_amount_list, save=2)
    #   红包领取个数
    red_receive_dict = {}
    red_receive_amount_dict = {}
    red_receive_match = {"race_cid": race_cid, 'record_flag': 1, "award_cid": {'$ne': None},
                         'draw_status': 0, 'member_cid': {'$ne': None},
                         'draw_dt': {'$gte': export_time_list[0].replace(hour=0, minute=0, second=0),
                                        '$lte': (export_time_list[-1] + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0)}}

    red_receive_cursor = RedPacketBox.sync_aggregate(
        [
            MatchStage(red_receive_match),
            lookup_stage,
            ProjectStage(**{
                'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$draw_dt"}},
                "member_cid": '$member_cid',
                "member_list": "$member_list",
                "award_amount": '$award_amount',
            }),
            MatchStage({'member_list': {'$ne': []}}),
            GroupStage({"daily_code": "$daily_code"}, receive_amount_list={'$push': '$award_amount'}, cid_list={'$push': '$member_cid'}, sum={'$sum': 1})
        ]
    )
    while True:
        try:
            red_packet = red_receive_cursor.next()
            if red_packet and red_packet.cid_list:
                amount_list = red_packet.receive_amount_list
                cid_list = list(set(red_packet.cid_list))
                print(len(cid_list), 'len')
                daily = red_packet.id.get('daily_code')
                for cid, amount in zip(cid_list, amount_list):
                    race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': cid, 'auth_address.city': {'$in': city_name_list}, 'auth_address.district': {'$in': dist_list}})
                    if race_mapping:
                        city = race_mapping.auth_address.get('city')
                        district = race_mapping.auth_address.get('district')
                        city_district = "{city}-{district}".format(city=city, district=district)
                        if daily not in red_receive_dict:
                            red_receive_dict[daily] = {city_district: 1}
                        else:
                            v_dict = red_receive_dict.get(daily)
                            if city_district not in v_dict:
                                v_dict[city_district] = 1
                            else:
                                v_dict[city_district] += 1
                        if daily not in red_receive_amount_dict:
                            red_receive_amount_dict[daily] = {city_district: amount}
                        else:
                            v_dict = red_receive_amount_dict.get(daily)
                            if city_district not in v_dict:
                                v_dict[city_district] = amount
                            else:
                                v_dict[city_district] += amount
        except StopIteration:
            break
        except Exception as e:
            raise e
    print(red_receive_dict, 'receive_cursor')
    print(red_receive_amount_dict, 'rece_amount')
    #  excel 填充每日领取个数
    write_excel_data(sheet, red_receive_dict, dis_map, export_time, red_receive_position_list, save=None)
    #  excel 填充每日领取金额
    write_excel_data(sheet, red_receive_amount_dict, dis_map, export_time, red_receive_amount_list, save=2)
    workbook.close()


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


if __name__ == '__main__':

    export_race_enter_position("3040737C97F7C7669B04BC39A660065D", "999")
    now = datetime.datetime.now()


#   六安市的参与人数，区县完全对应
#   六安市的参与次数，区县完全对应

#  quantity_time_dict = {'20190702': {'叶集区': 20}, '20190703': {'舒城县': 30}}
#  贵州cid F742E0C7CA5F7E175844478D74484C29
#  安徽cid 3040737C97F7C7669B04BC39A660065D
#  六安cid  CA755167DEA9AA89650D11C10FAA5413