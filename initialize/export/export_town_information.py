import datetime

import xlsxwriter

from commons.common_utils import str2datetime
from db.models import RaceMapping, AdministrativeDivision, ReportRacePeopleStatistics, Member, MemberCheckPointHistory, \
    Company, RaceGameCheckPoint
from initialize.export.export_race_people_information import get_export_param
from motorengine import ASC, DESC
from motorengine.stages import LookupStage, MatchStage, ProjectStage, GroupStage, SortStage
from motorengine.stages.add_fields_stage import AddFieldsStage

now = format(datetime.datetime.now(), "%Y-%m-%d%H:%M")

district_title_list = ['舒城县', '叶集区', '霍邱县', '金安区', '裕安区', '金寨县', '开发区', '霍山县']


def export_town_member_information(city_race_cid, prov_race_cid):
    """
    导出六安市个人信息
    :param prov_race_cid:
    :param city_race_cid
    :return:
    """
    # district_title_list = AdministrativeDivision.sync_distinct('title', {'parent_code': "341500"})
    district_title_list = ['舒城县', '叶集区', '霍邱县', '金安区', '裕安区', '金寨县', '开发区', '霍山县']
    match = {'race_cid': {'$in': [prov_race_cid, city_race_cid]},
             "auth_address.province": {'$ne': None},
             'auth_address.city': '六安市', "record_flag": 1, "auth_address.district": {'$in': district_title_list},
             'auth_address.town': {'$ne': None}}

    print(district_title_list)
    prov_match = {'race_cid': prov_race_cid,
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': '六安市', "record_flag": 1, "auth_address.district": {'$in': district_title_list}}
    city_match = {'race_cid': city_race_cid,
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': '六安市', "record_flag": 1, "auth_address.district": {'$in': district_title_list},
                  'auth_address.town': {'$ne': None}}
    count_match = {'race_cid': {'$in': [prov_race_cid, city_race_cid]},
                   "city": "六安市",
                   'district': {'$in': district_title_list}, 'town': {'$ne': None}}
    prov_count_match = {'race_cid': "3040737C97F7C7669B04BC39A660065D",
                        "province": {'$ne': None},
                   "city": "六安市",
                   'district': {'$in': district_title_list}}
    # # 六安市的数据 包括安徽省六安市的数据和六安市活动数据
    excel_title = "liuan{time}.xlsx".format(time=now)
    workbook = xlsxwriter.Workbook(excel_title)
    # #  乡镇得每日新增人数
    write_daily_increase_people(workbook, city_match, prov_match, city_race_cid, sheet_name="每日新增人数")
    # #  每日参与人次
    daily_people_liuan_anhui(workbook, prov_count_match, sheet_name="每日参与人次")
    # people_count(prov_race_cid, city_race_cid, workbook)
    base_match = {'race_cid': {'$in': [prov_race_cid, city_race_cid]},
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': '六安市', "record_flag": 1, "auth_address.district": {'$in': district_title_list}}
    export_race_member_base_information(prov_match, city_match, workbook, base_match, title="六安市",
                                        district_title_list=district_title_list,
                                        prov_race_cid=prov_race_cid, city_race_cid=city_race_cid)
    write_daily_increase_company_pass_people(workbook, prov_race_cid, city_race_cid, "每日新增通关人数")
    company_math = {'race_cid': {'$in': [prov_race_cid, city_race_cid]},
                    "auth_address.province": {'$ne': None},
                    'auth_address.city': '六安市', "record_flag": 1,
                    "auth_address.district": {'$in': district_title_list},
                    }
    # # # # # #  单位得每日新增人次，每日新增次数，每日通关人数
    write_daily_increase_company_people(workbook, company_math)
    daily_code_company_count(workbook, company_math, city_race_cid)
    workbook.close()


# def make_data():
#     """
#     造六安市数据
#     :param race_cid:
#     :return:
#     """
#     #  六安市得race_cid
#     city_race_cid = "0456603A25199D2B543C9A1B53B99666"
#     race_cid = "3040737C97F7C7669B04BC39A660065D"
#     race_mapping_list = RaceMapping.sync_find({'race_cid': race_cid, 'auth_address.town': {'$eq': None}}).to_list(None)
#     race_report_list = ReportRacePeopleStatistics.sync_find({'race_cid': race_cid, 'town': {'$eq': None}}).to_list(None)
#     district_list = AdministrativeDivision.sync_find({'parent_code': "341500"}).to_list(None)
#     district_code_list = [district.code for district in district_list]
#     town_list = AdministrativeDivision.sync_find({"parent_code": {'$in': district_code_list}}).to_list(None)
#     town_name_list = [town.title for town in town_list]
#     for race_mapping in race_mapping_list:
#         race_mapping.auth_address['town'] = random.choice(town_name_list)
#         race_mapping.sync_save()
#     for report in race_report_list:
#         report.town = random.choice(town_name_list)
#         report.sync_save()

def generate_excel_information_head(sheet, character_format):
    """
    生成个人信息表中表头信息
    :param sheet:
    :param character_format:
    :return:
    """
    sheet.merge_range(0, 0, 0, 1, '昵称', character_format)
    sheet.write_string(0, 2, '地区', character_format)
    sheet.merge_range(0, 3, 0, 4, '手机号码', character_format)
    sheet.write_string(0, 5, "正确率", character_format)
    return sheet


def generate_excel_statics_head(sheet, character_format):
    """
    生成统计表表头信息
    :param sheet:
    :param character_format:
    :return:
    """
    sheet.merge_range(0, 0, '省份', character_format)
    sheet.write_string(0, 1, '城市', character_format)
    sheet.merge_range(0, 2, '区县', character_format)
    sheet.write_string(0, 3, "乡镇", character_format)
    return sheet


def write_daily_increase_people(book, match, prov_match, city_race_cid, sheet_name='每日新增参与人数'):
    """
    每日新增人数
    :param book:
    :param sheet_name:
    :param match
    :param prov_match
    :return:
    """
    print('start ==========')
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    sheet = book.add_worksheet(sheet_name)
    address_sort = SortStage([('_id.district', ASC), ('_id.town', ASC)])
    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'auth_address': "$auth_address",
             "member_cid": "$member_cid",
             "member_list": "$member_list"
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'town': '$auth_address.town', 'district': '$auth_address.district'},
                    sum={'$sum': 1},
                    cid_list={'$push': '$member_cid'},
                    auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])], allowDiskUse=True)
    address_list = RaceMapping.sync_aggregate(
        [
            MatchStage(match),
            lookup_stage,
            ProjectStage(**{
                'auth_address': "$auth_address",
                "member_list": "$member_list"
            }), MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {'town': '$auth_address.town', 'district': '$auth_address.district', 'city': '$auth_address.city'}),
            address_sort
        ]
    )
    prov_cursor = RaceMapping.sync_aggregate(
        [MatchStage(prov_match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'auth_address': "$auth_address",
             "member_cid": "$member_cid",
             "member_list": "$member_list",
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'},
                    sum={'$sum': 1},
                    cid_list={'$push': '$member_cid'},
                    auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])], allowDiskUse=True)
    #  六安市没有乡镇的数据
    city_match = {'race_cid': city_race_cid,
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': '六安市', "record_flag": 1,
                  "auth_address.district": {'$in': ['舒城县', '叶集区', '霍邱县', '金安区', '裕安区', '金寨县', '开发区', '霍山县']},
                  "auth_address.town": {'$eq': None}}
    city_cursor = RaceMapping.sync_aggregate(
        [MatchStage(city_match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'auth_address': "$auth_address",
             "member_list": "$member_list",
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'},
                    sum={'$sum': 1},
                    auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])], allowDiskUse=True)
    prov_dict = {}
    #  每日参与member_cid_list  {'2019-05-20': ["1111", "222"]}
    # member_cid_daily_mapping = {}
    city_dict = {}
    # 六安没有乡镇的数据
    while True:
        try:
            data = city_cursor.next()
            district = data.id.get('district')
            if district not in city_dict:
                city_dict[district] = data.sum
            else:
                city_dict[district] += data.sum
        except StopIteration:
            break
        except Exception as e:
            raise e
    print(city_dict, 'city')
    #  安徽六安
    while True:
        try:
            data = prov_cursor.next()
            # cid_list = list(set(data.cid_list))
            # print(member_cid, 'cid123')
            district = data.id.get('district')
            # daily_code = data.id.get("daily_code")
            # member_list = data.id.get('cid_list')
            # print(data.cid_list, 'cid_list333')
            # if daily_code not in member_cid_daily_mapping:
            #     member_cid_daily_mapping[daily_code] = list(set(cid_list))
            # else:
            #     member_cid_daily_mapping[daily_code] += list(set(cid_list))
            # _date = transform_date(daily_code)
            # if daily_code == "20190628":
            #     print("1")
            # _count = len(cid_list)
            # for cid in cid_list:
            #     race_mapping = RaceMapping.sync_find_one({"auth_address.city": "六安市", "member_cid": cid, "race_cid": city_race_cid,                     'created_dt': {'$lte': _date}})
            #     if race_mapping:
            #         _count -= 1
            #         cid_list.remove(cid)
            # if daily_code not in member_cid_daily_mapping:
            #     member_cid_daily_mapping[daily_code] = cid_list
            # else:
            #     member_cid_daily_mapping[daily_code] += cid_list
            # for member_cid in member_list:
            #     pass
            if district not in prov_dict:
                prov_dict[district] = data.sum
            else:
                prov_dict[district] += data.sum
        except StopIteration:
            break
        except Exception as e:
            raise e
    # print(member_cid_daily_mapping, 'map123')
    # for k, v in prov_dict.items():
    #     prov_dict[k] = len(list(set(v)))
    print(prov_dict, 'prov')
    # prov_dict = {'裕安区': 533, '金安区': 314, '舒城县': 229, '霍邱县': 106, '叶集区': 29, '霍山县': 1414, '金寨县': 173}
    # prov_dict = {'裕安区': 541, '金安区': 322, '舒城县': 234, '霍邱县': 106, '叶集区': 29, '霍山县': 1430, '金寨县': 180}
    # _total_prov_dict = {}
    # key_list = list(member_cid_daily_mapping.keys())
    # val_list = list(member_cid_daily_mapping.values())
    # for k, v in member_cid_daily_mapping.items():
    #     index = key_list.index(k)
    #     _total_prov_dict[k] = val_list[:index + 1]
    #
    # for k, v in _total_prov_dict.items():
    #     _list = []
    #     for cid_list in v:
    #         _list += cid_list
    #     _total_prov_dict[k] = list(set(_list))

    print(prov_dict, 'dict1')
    dis_map = {}
    for index, address in enumerate(address_list):
        sheet.write_string(index + 1, 0, "六安市")
        sheet.write_string(index + 1, 3, address.id.get('town'))
        if address.id.get('district') not in dis_map:
            dis_map[address.id.get('district')] = [address.id.get('town')]
        else:
            dis_map[address.id.get('district')] += [address.id.get('town')]
    #  乡镇列表
    town_list = []
    for town in dis_map.values():
        for t in town:
            if t not in town_list:
                town_list.append(t)

    print(town_list, 'town')
    address_map = dict(zip(town_list, range(1, len(town_list) + 1)))
    #  {'叶集区': 5, '舒城县': 5}
    count_map = {}
    for k, v in dis_map.items():
        if k not in count_map:
            count_map[k] = len(list(set(v)))
    print(dis_map, 'map1')
    #  所有得乡镇和区县对应信息
    district_map = get_all_district_town_map()
    #  六安市没有填乡镇的乡镇对应信息
    for k, v in dis_map.items():
        if k in district_map:
            a = list(set(district_map[k]) - set(dis_map[k]))
            district_map[k] = a
    last_dis = list(dis_map.keys())[-1]
    print(last_dis)
    last_value = district_map[last_dis]
    new_mapping = {}
    new_mapping[last_dis] = last_value
    for k, v in district_map.items():
        if k != last_dis:
            new_mapping[k] = v
    print(new_mapping, 'new')
    print(district_map, 'no diff')
    print(address_map, 'map2')
    print(count_map, 'count_map12')
    quantity_list = list(count_map.values())
    name_list = list(count_map.keys())
    for index, title in enumerate(list(count_map.keys())):
        if index == 0:
            for pos in range(1, quantity_list[0] + 1):
                sheet.write_string(pos, 1, title)
        else:
            for pos in range(sum(quantity_list[0: index]) + 1, sum(quantity_list[0: index + 1]) + 1):
                sheet.write_string(pos, 1, title)
    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    sheet.write_string(0, 2, '总数')
    sheet.write_string(0, 3, '乡镇')
    daily_list = ["1"]
    county_map = {}
    v_list = list()
    prize_list = []
    _max_row = 0
    city_map = {}
    _total_list = []
    while True:
        try:
            data = cursor.next()
            _current_row = None
            cid_list = list(set(data.cid_list))
            title = data.id.get('town')
            district = data.id.get('district')
            daily_code = data.id.get("daily_code")
            city_cid_list = []
            # if daily_code in member_cid_daily_mapping:
            #     prov_cid_list = _total_prov_dict.get(daily_code)
            #     # for cid in prov_cid_list:
            #     #     if cid not in _total_list:
            #     #         _total_list.append(cid)
            #     # _index = list(member_cid_daily_mapping.keys()).index(daily_code)
            #     # print(_index)
            #     # for index, i in enumerate(list(member_cid_daily_mapping.values())[:_index + 1]):
            #     #     print(index)
            #     #     print(i)
            #     #     for cid in i:
            #     #         if cid not in _total_list:
            #     #             _total_list.append(cid)
            #     city_cid_list = list(set(cid_list) - set(prov_cid_list))
            # city_data = len(city_cid_list)
            if title not in prize_list:
                prize_list.append(title)

            # _current_row = len(prize_list)
            if title is None:
                title = '未知'
            if district not in city_map:
                city_map[district] = data.sum
            else:
                city_map[district] += data.sum
            _current_row = address_map.get(title)

            # if title not in prize_list:
            #     prize_list.append(title)
            # _current_row = len(prize_list)

            district = data.auth_address.get('district')
            if not district:
                continue
            sheet.write_string(_current_row, 0, "六安市")
            # sheet.write_string(_current_row, 1, district)
            ad_city = AdministrativeDivision.sync_find_one({'title': district})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
            for _c in _county:
                county_map[_c] = district

            sheet.write_string(_current_row, 3, title)
            #
            # else:
            #     _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list) + 2
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 3

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e
    print(city_map, '2222')
    #  没有乡镇的起始行'
    max_row = sum(quantity_list)
    no_town_start_row = sum(quantity_list) + 1
    for k, v_list in new_mapping.items():
        for index, town in enumerate(v_list):
            max_row += 1
            sheet.write_string(max_row, 1, k)
            sheet.write_string(max_row, 3, town)
            sheet.write_string(max_row, 0, '六安')
    print(max_row, 'max')
    print(no_town_start_row, 'no_strt')
    total_map = {}
    for k, v in prov_dict.items():
        if k not in total_map:
            total_map[k] = v
        else:
            total_map[k] += v

    for k, v in city_map.items():
        if k not in total_map:
            total_map[k] = v
        else:
            total_map[k] += v
    for k, v in city_dict.items():
        if k not in total_map:
            total_map[k] = v
        else:
            total_map[k] += v
    print(total_map, '123')
    for index, num in enumerate(quantity_list):
        if index == 0:
            name = name_list[0]
            sheet.write_number(1, 2, total_map.get(name))
        else:
            name = name_list[index]
            sheet.write_number(sum(quantity_list[0: index]) + 1, 2, total_map.get(name))
        # if _max_row:
        sheet.write_string(max_row + 2, 0, '总和')
        sheet.write_number(max_row + 2, 1, sum(list(total_map.values())))
    count = len(daily_list) + 2
    sheet.write_string(0, count, "合计")
    for i in range(2, _max_row + 2):
        start = convert(3)
        start = start + str(i)
        end = convert(len(daily_list) + 1)
        end = end + str(i)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(i - 1, len(daily_list) + 2, formula)


def write_daily_increase_company_people(book, match, sheet_name="单位每日新增参与人数"):
    """
    单位每日新增参与人数
    :param book:
    :param match:
    :param sheet_name:
    :return:
    """
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'company_cid': "$company_cid",
             "member_list": "$member_list"
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'company_cid': '$company_cid'}, sum={'$sum': 1}),

         SortStage([('_id.daily_code', ASC)])], allowDiskUse=True)
    sheet.write_string(0, 0, "单位")
    daily_list = []
    prize_list = []
    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            company_cid = data.id.get('company_cid')
            print(company_cid, '123')
            if company_cid is None:
                continue
            else:
                company = Company.sync_get_by_cid(company_cid)
                title = company.title
            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, title)
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e
    print(prize_list, 'prize')
    print(len(prize_list), 'len')
    print(_max_row)
    company = Company.sync_distinct('title', {'race_cid': "CA755167DEA9AA89650D11C10FAA5413"})
    extra_company = list(set(company) - set(prize_list))
    print(extra_company)
    for i in extra_company:
        sheet.write_string(_max_row + 1, 0, i)
        _max_row += 1
    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))
    count = len(daily_list) + 1
    sheet.write_string(0, count, "合计")
    for i in range(2, _max_row + 2):
        start = convert(1)
        start = start + str(i)
        end = convert(len(daily_list))
        end = end + str(i)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(i - 1, len(daily_list) + 1, formula)


def write_daily_increase_company_pass_people(book, prov_race_cid, city_race_cid, sheet_name):
    """
    每日新增通关人数
    :param book:
    :param sheet_name:
    :return:
    """
    prov_last_checkpoint_cid = "05528C744EE42E838F7EE9D69070E6AA"  # 安徽的最后一关
    city_last_checkpoint_cid = "AFC97D7D354C1D44BF64A5DDAB76E8D7"  # 六安市的最后一关  # local D4634A1E3FF9DFEA98DD11169E6BFE6C  online  AFC97D7D354C1D44BF64A5DDAB76E8D7
    match_stage = MatchStage({'check_point_cid': prov_last_checkpoint_cid, 'status': 1, 'record_flag': 1})
    city_match_stage = MatchStage({'check_point_cid': city_last_checkpoint_cid, 'status': 1, 'record_flag': 1})
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    check_point_cursor = MemberCheckPointHistory.sync_aggregate([match_stage, lookup_stage], allowDiskUse=True)
    city_cursor = MemberCheckPointHistory.sync_aggregate([city_match_stage, lookup_stage], allowDiskUse=True)
    member_cid_list = []
    time_list = []
    dis_mapping = {}
    mapping = {}
    _prov_mapping = {}
    while True:
        try:
            check_point = check_point_cursor.next()
            if check_point.member_list:
                member = check_point.member_list[0]
                race_mapping = RaceMapping.sync_find_one(
                    {'race_cid': prov_race_cid, 'member_cid': member.cid})
                if race_mapping:
                    if race_mapping.auth_address and race_mapping.auth_address.get('district'):
                        if check_point.member_cid not in member_cid_list and race_mapping.auth_address['city'] == "六安市":
                            district = race_mapping.auth_address.get('district')
                            member_cid_list.append(check_point.member_cid)
                            created_time = format(check_point.created_dt, "%Y-%m-%d")
                            if created_time not in time_list:
                                time_list.append(created_time)
                                dis_mapping[created_time] = 1
                                mapping[created_time] = [race_mapping.auth_address.get('district')]
                            else:
                                dis_mapping[created_time] += 1
                                mapping[created_time] += [race_mapping.auth_address.get('district')]
                            if district not in _prov_mapping:
                                _prov_mapping[district] = 1
                            else:
                                _prov_mapping[district] += 1
        except StopIteration:
            break
        except Exception as e:
            raise e
    # member_cid_list = ['3C5E329DA104C554D51A0532CD0EFFB3', 'EA909687E71BDF3C9F74CC2673A37E16', '80B7FD7168C9C9A7EA5E10C280D4B5BE', 'D8486A2DCC3736A887C54A2C04E22666', '4B8B2301D7FED3318AFA28D6B8E3D670', 'E9CE1CE4186447C1DAA80E2F05B926AC', '2AE05D828AAF79081182CE03FB5A2232', '9E6F5FD9C39EE0B75C0C3FC2F6EAC48B', '718D31AF2AAE5B294EB84D0F1D515730', 'C66D2FB4BA63FBD08F0140B86DB46AC2', '4D678389D135C60A5E87EB4E77BA6F5C', '5559E57E3A31EC8382CF4AFCE43632D7', 'BE3235AE8817AFA370980477DF28D872', '96FE9E516D95B8436C9028C96CDAFC37', '5DB1AD29F4BC666A540C560EC85FE89B', '557FF29F9892052D952F5671FD15F481', '8AE03DEE16A22F82FF367D64A2F72E04', '78F01B08544A2907996CFFED0F8F8E13', '85239C6F731E71377E18942819CA8464', '8B7A34694537B75C8BEEB252311956BD', 'E294F3A0B5D1E6C735F3DEAB863CA788', 'FE9502D3322CA19DECA4FFD7A982C22D', 'AEE8F0F3BC55A55AA48641689AC4F227', '8F4205702E772B576A2A62B747383F97', '4BDC9F87E5D6D010CC25E353025264CD', '561515B1EAC40267FEF6CBCA3DBC1AD9', '471D0BF6709C28CB12D1C3C927A20CFB', '3800D7C5667F483A4A6DC1C1B09EA289', '2B891790814F0D94427D1CA28D4CD449', 'CA2AD991BC000E159A5E20C224E43AEA', 'A38C4D4DF2A32F73634D896CD73B2C83', 'B2AACE40A5F6834B12466EE40EADAFA6', '2C49EB9D408E2E9447F1DBBF3207620D', 'F2C4DA839703AE6D288AFC47CE68C8BF', 'AD154B9CA22048419CECB486F18C2900', 'C4196D49FE4DC4F41495E7B4A6E24A51', '03A19AA5A90C33784C27370E5BFEBFC0', '3E087C7998DB23F8E6273B03A255C2B6', '5EBC66C83A6F05B41469417C0E9C18E2', 'B4126F4600683C7B66F53039410A2162', 'CAC6A0116109C1B97FAC8CB564BF41FA', 'DF85229FFC5703485CBC45622D4BB249', 'B648B4C592E9B7678BD395810DA5161B', '5C7BFBE4DB144D96F8D16775E6808B8F', '72460A30636F76495C7BDCC6D7913012', '66F023DE4970D4AFBD8BD316C796753C', '976BD6683E70BBB8139BEF4F080F52F0', '556E05E8D85857DCECA0CE766AA6E7F0', '8530CA5163FEF156498CAF0D8EB3EBCB', '216ADD2865120A1FC61A8D3D6CB14F83', '1EE2C2296BF849B2818CCB70BA43F11F', '54B609EE8FD22BC017CFFFD83C594EA9', '2F1BF5241F05736880371F8EC8B5E537', '334F489ABF429132ECC751F4E4685BC2', '559FAE63A22C4B748E4490D647B8F428', '020A09359496227CBDD765405277C62F', 'C3941BE7FC8AA0A50FA8C0B8B7E62C57', '08EC1C6BAAED9348E6BA67E6417133E3', '7A571007812B3A121A72EA2F091BB52D', '3A6F3D1B8B2EE1456E433B1F02A63E8D', '238C74CD138D8B51CD54D8548FDC36FE', 'F52E37EE61944C182FD5B2745FC2DCB2', 'B6850BA77CCFCA92DBCF3123A8A5D829', '3441DAC739FE8F3E90097D8F0CE04DB5', 'CC4272B922BFC74D642228457108652A', '9C42EE5DC5136CD28F7FBAF5CFA9E3A1', '5487D0441F818866D82B0C358EEAD937', '56068D7936CE3A2ABE517D14E298DC8E', '8C0434846F79D8130125D958305FDA96', '4AE1BE2A962BC218B6669018731D769E', 'AF3544BE855D689748D9ED616446838C', 'A4312EF6D821CAEAABE6F79032750511', 'AA6B6EA9B52399976C7BB11FFABFAC76', '82983A1E996B8F502CC6ED62971830D9', 'D5BF77B1076D5597FE18FE12189554B8']
    # print(dis_mapping, 'dict1')
    # print(member_cid_list, 'member_cid')
    # dis_mapping = {'2019-05-20': 3, '2019-05-22': 2, '2019-05-25': 1, '2019-06-12': 1, '2019-06-13': 2, '2019-06-14': 2,
    #                '2019-06-17': 2, '2019-06-18': 3, '2019-06-19': 3, '2019-06-20': 2, '2019-06-21': 5, '2019-06-22': 2,
    #                '2019-06-24': 1, '2019-06-25': 2, '2019-06-26': 4, '2019-06-27': 4, '2019-06-28': 8, '2019-06-29': 5,
    #                '2019-06-30': 6, '2019-07-01': 1, '2019-07-02': 6, '2019-07-03': 9, '2019-07-04': 1}
    # mapping = {'2019-05-20': ['裕安区', '裕安区', '裕安区'], '2019-05-22': ['金安区', '金安区'], '2019-05-25': ['金安区'],
    #            '2019-06-12': ['裕安区'], '2019-06-13': ['金寨县', '金寨县'], '2019-06-14': ['舒城县', '霍山县'],
    #            '2019-06-17': ['舒城县', '霍山县'], '2019-06-18': ['霍邱县', '霍邱县', '裕安区'], '2019-06-19': ['舒城县', '霍山县', '霍邱县'],
    #            '2019-06-20': ['霍山县', '金安区'], '2019-06-21': ['金寨县', '舒城县', '舒城县', '舒城县', '舒城县'],
    #            '2019-06-22': ['裕安区', '霍山县'], '2019-06-24': ['舒城县'], '2019-06-25': ['舒城县', '裕安区'],
    #            '2019-06-26': ['金安区', '霍山县', '霍邱县', '霍山县'], '2019-06-27': ['霍山县', '舒城县', '霍山县', '裕安区'],
    #            '2019-06-28': ['霍邱县', '金安区', '舒城县', '霍山县', '舒城县', '舒城县', '金寨县', '舒城县'],
    #            '2019-06-29': ['舒城县', '裕安区', '金安区', '金安区', '裕安区'],
    #            '2019-06-30': ['舒城县', '霍山县', '金安区', '金安区', '舒城县', '霍邱县'], '2019-07-01': ['金寨县'],
    #            '2019-07-02': ['金安区', '金安区', '裕安区', '舒城县', '霍山县', '金寨县'],
    #            '2019-07-03': ['金寨县', '霍山县', '裕安区', '舒城县', '金安区', '霍邱县', '霍山县', '霍山县', '霍山县'], '2019-07-04': ['霍山县']}
    # print(mapping, 'map1')
    # _prov_mapping = {'裕安区': 12, '金安区': 13, '金寨县': 7, '舒城县': 19, '霍山县': 17, '霍邱县': 7}
    print(_prov_mapping, '_prov1')
    # dis_mapping = {'2019-05-20': 3, '2019-05-22': 2, '2019-05-25': 1, '2019-06-12': 1, '2019-06-13': 2, '2019-06-14': 2,
    #                '2019-06-17': 2, '2019-06-18': 3, '2019-06-19': 1}
    # mapping = {'2019-05-20': ['裕安区', '裕安区', '裕安区'], '2019-05-22': ['裕安区', '裕安区'], '2019-05-25': ['裕安区'],
    #            '2019-06-12': ['裕安区'], '2019-06-13': ['金寨县', ''
    #                                                         '裕安区'], '2019-06-14': ['裕安区', '裕安区'],
    #            '2019-06-17': ['舒城县', '霍山县'], '2019-06-18': ['霍邱县', '裕安区', '裕安区'], '2019-06-19': ['舒城县']}
    sheet = book.add_worksheet(sheet_name)
    district_list = []
    for dis_list in list(mapping.values()):
        for district in dis_list:
            if district not in district_list:
                district_list.append(district)
    print(district_list, 'dis_list')
    # order_map = dict(zip(district_list, range(1, len(district_list) + 1)))
    # print(order_map, 'order')
    # prov_mapping = {}
    # for k, v in mapping.items():
    #     if k not in prov_mapping:
    #         prov_mapping[k] = len(v)
    #     else:
    #         prov_mapping[k] += len(v)
    # print(prov_mapping)
    # print(sum(list(dis_mapping.values())))
    city_member_list = []
    city_time_list = []
    city_member_dict = {}
    city_mapping = {}
    _city_dict = {}
    no_town_time_list = []
    while True:
        try:
            check_point = city_cursor.next()
            if check_point.member_list:
                member = check_point.member_list[0]
                race_mapping = RaceMapping.sync_find_one(
                    {'race_cid': city_race_cid, 'member_cid': member.cid})
                if race_mapping:
                    if race_mapping.auth_address and race_mapping.auth_address.get(
                            'town') and race_mapping.auth_address.get("district") in district_title_list:
                        if check_point.member_cid not in city_member_list and check_point.member_cid not in member_cid_list and race_mapping.auth_address[
                                'city'] == "六安市":
                            city_member_list.append(check_point.member_cid)
                            created_time = format(check_point.created_dt, "%Y-%m-%d")
                            if created_time not in city_time_list:
                                city_time_list.append(created_time)
                                city_member_dict[created_time] = 1
                                city_mapping[created_time] = [race_mapping.auth_address.get('town')]
                            else:
                                city_member_dict[created_time] += 1
                                city_mapping[created_time] += [race_mapping.auth_address.get('town')]
                    elif race_mapping.auth_address and race_mapping.auth_address.get("district") in district_title_list:
                        if check_point.member_cid not in city_member_list and check_point.member_cid and check_point.member_cid not in member_cid_list and race_mapping.auth_address[
                                'city'] == "六安市":
                            member_cid_list.append(check_point.member_cid)
                            city_member_list.append(check_point.member_cid)
                            created_time = format(check_point.created_dt, "%Y-%m-%d")
                            district = race_mapping.auth_address.get('district')
                            if district not in _city_dict:
                                _city_dict[district] = 1
                            else:
                                _city_dict[district] += 1
                            # if created_time not in no_town_time_list:
                            #     no_town_time_list.append(created_time)
                            #     # _city_dict[created_time] = 1
                            #
                            #     _city_dict[race_mapping.get(district)] = 1
                            # else:
                            #     _city_dict[created_time] += 1
                            #     _city_dict[race_mapping.get(district)] += 1

        except StopIteration:
            break
        except Exception as e:
            raise e
    print(city_member_dict, 'dict2')  # 55个  填了乡镇通关的
    print(_city_dict, '+city')   # 12 没填乡镇通关的
    for k, v in _city_dict.items():
        if k in _prov_mapping:
            _prov_mapping[k] += v
        else:
            _prov_mapping[k] = v
    print(_prov_mapping, 'map2')
    print(sum(list(city_member_dict.values())))
    #  整合安徽六安的数据和六安市活动的数据
    total_mapping = {}
    for k, v in city_mapping.items():
        if k not in total_mapping:
            total_mapping[k] = v
        else:
            total_mapping[k] += v
    print(total_mapping, 'total')
    _town_dict = {}
    for k, v_list in total_mapping.items():
        for title in v_list:
            _town = AdministrativeDivision.sync_find_one({'record_flag': 1, 'title': title, "level": "T"})
            if _town:
                _district = AdministrativeDivision.sync_find_one({'record_flag': 1, 'code': _town.parent_code})
                if _district.title in district_list:
                    if _district.title not in _town_dict:
                        _town_dict[_district.title] = 1
                    else:
                        _town_dict[_district.title] += 1
                else:
                    district_list.append(_district)
            elif not _town and title == "顺和镇":
                _district = "裕安区"
                if _district in district_list:
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
                else:
                    district_list.append(_district)
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
            elif not _town and title in ['教育系统',
                    '人民路小学',
                    '三里桥小学',
                    '皖西路小学',
                    '梅山路小学',
                    '清水河学校',
                    '金安路学校',
                    '人民路小学东校',
                    '区卫健委',
                    '市第四人民医院',
                    '区妇幼保健院',
                    '区疾控中心',
                    '区卫生监督所',
                    '区妇幼保健计划生育服务中心'
                    ]:
                _district = "金安区"
                if _district in district_list:
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
                else:
                    district_list.append(_district)
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
            else:
                _district = "未知"
                if _district in district_list:
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
                else:
                    district_list.append(_district)
                    if _district not in _town_dict:
                        _town_dict[_district] = 1
                    else:
                        _town_dict[_district] += 1
    print(_town_dict, '_town_dict1')
    # total_mapping = {'2019-05-22': ['三元镇', "鼓楼街道"], '2019-05-23': ["三里桥小学", "独山镇", "史河街道", "姚李镇"]}
    sheet.write_string(0, 0, "城市")
    sheet.write_string(0, 1, "区县")
    sheet.write_string(0, 2, "总数")
    sheet.write_string(0, 3, "乡镇")
    town_total_list = []
    for town_list in total_mapping.values():
        for town in town_list:
            if town not in town_total_list:
                town_total_list.append(town)
    # excel城镇的具体未知
    position_mapping = dict(zip(town_total_list, range(1, len(town_total_list) + 1)))
    print(position_mapping, 'map2')
    print(town_total_list)
    # district_list.append("叶集区")
    temp_map = {}
    for town in town_total_list:
        _town = AdministrativeDivision.sync_find_one({'record_flag': 1, 'title': town, "level": "T"})
        if _town:
            _district = AdministrativeDivision.sync_find_one({'record_flag': 1, 'code': _town.parent_code})
            if _district.title in district_list:
                if _district.title not in temp_map:
                    temp_map[_district.title] = [town]
                else:
                    temp_map[_district.title] += [town]
            else:
                district_list.append(_district)
        elif not _town and town == "顺和镇":
            _district = "裕安区"
            if _district in district_list:
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
            else:
                district_list.append(_district)
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
        # sheet.write_string(1 + index, 1, "裕安区")
        elif not _town and town in ["梅山路小学", "三里桥小学", "金安路学校", "教育系统"]:
            _district = "金安区"
            if _district in district_list:
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
            else:
                district_list.append(_district)
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
        else:
            _district = "未知"
            if _district in district_list:
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
            else:
                district_list.append(_district)
                if _district not in temp_map:
                    temp_map[_district] = [town]
                else:
                    temp_map[_district] += [town]
    print(temp_map, 'temp')

    s = sorted(temp_map.items(), key=lambda x: district_list.index(x[0]))
    #  {'裕安区': ['鼓楼街道', '独山镇'], '叶集区': ['三元镇', '史河街道', '姚李镇']}
    temp_map = dict(s)
    #  {'裕安区': 3, '叶集区': 3}
    _count_map = {}
    for k, v in temp_map.items():
        if k not in _count_map:
            _count_map[k] = len(list(set(v)))
        else:
            _count_map[k] += len(list(set(v)))
    print(_count_map, '_co')
    print(temp_map)
    #  通过区排序的乡镇列表
    city_town_list = []
    for k, v in temp_map.items():
        for town in v:
            if town not in city_town_list:
                city_town_list.append(town)
    print(city_town_list, 'city_town')
    #  整合安徽六安的数据
    _total_mapping = {}
    for k, v in _prov_mapping.items():
        if k not in _total_mapping:
            _total_mapping[k] = v
        else:
            _total_mapping[k] += v

    for k, v in _town_dict.items():
        if k not in _total_mapping:
            _total_mapping[k] = v
        else:
            _total_mapping[k] += v
    print(_total_mapping, '_total')
    _name_list = list(_count_map.keys())
    count_list = list(_count_map.values())
    #  excel 写入乡镇信息
    for index, city_town in enumerate(city_town_list):
        sheet.write_string(index + 1, 3, city_town)
    #  excel写入区县信息
    for index, city_town in enumerate(_name_list):
        if index == 0:
            sheet.write_string(1, 1, city_town)
            sheet.write_number(1, 2, _total_mapping.get(city_town))
        else:
            sheet.write_string(sum(count_list[:index]) + 1, 1, city_town)
            sheet.write_number(sum(count_list[:index]) + 1, 2, _total_mapping.get(city_town))
    # 没有乡镇的区县
    no_town_dis_list = list(set(list(_total_mapping.keys())) - set(list(_count_map.keys())))
    print(no_town_dis_list, 'dis_list23')
    for index, title in enumerate(no_town_dis_list):
        sheet.write_string(sum(count_list) + 1 + index, 1, title)
        sheet.write_string(sum(count_list) + 1 + index, 0, "六安市")
        sheet.write_number(sum(count_list) + 1 + index, 2, _total_mapping.get(title))
    for index, town in enumerate(town_total_list):
        #  横向求和
        start = convert(4)
        start = start + str(index + 2)
        end = convert(len(list(total_mapping.keys())) + 3)
        end = end + str(index + 2)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(index + 1, len(list(total_mapping.keys())) + 4, formula)
        sheet.write_string(1 + index, 0, "六安市")
    sheet.write_string(sum(list(_count_map.values())) + len(no_town_dis_list) + 1, 0, "总计")
    sheet.write_number(sum(list(_count_map.values())) + len(no_town_dis_list) + 1, 1,
                       sum(list(_total_mapping.values())))
    for index, date in enumerate(list(total_mapping.keys())):
        sheet.write_string(0, 4 + index, date)
        town_list = total_mapping.get(date)
        if not town_list:
            continue
        for town in town_list:
            row = position_mapping.get(town)
            data = town_list.count(town)
            sheet.write_number(row, 4 + index, data)
    print(total_mapping, '12345')
    sheet.write_string(0, len(list(total_mapping.keys())) + 4, "总计")
    # total_start = convert(len(list(total_mapping.keys())) + 2) + "2"
    # print(total_mapping, 'mappinigggg123')
    # total_end = convert(len(list(total_mapping.keys())) + 4) + str(len(city_town_list) + 1)
    # total_formula = "=SUM(" + total_start + ":" + total_end + ")"
    # sheet.write_formula(sum(list(_count_map.values())) + len(no_town_dis_list)+ 1, 1, total_formula)


def write_sheet_enter_data(book, match, sheet_name, count_type='$people_num'):
    """
    每日参与人次
    :param book:
    :param sheet_name:
    :param match
    :param count_type:
    :return:
    """

    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'town': '$town'}, sum={'$sum': count_type},
                             district={'$first': '$district'})
    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    sheet.write_string(0, 2, "乡镇")
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 3, daily_code)
        daily_map[daily_code] = index + 3

    district_list = ReportRacePeopleStatistics.sync_distinct('town', match)
    district_map = {}
    for index, district in enumerate(district_list):
        sheet.write_string(index + 2, 2, district if district else '其他')
        district_map[district if district else '其他'] = index + 2

    cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(match), group_stage], allowDiskUse=True)

    county_map = dict()
    v_list = list()
    _max_row = 0
    while True:
        try:
            stat = cursor.next()

            district = stat.district if stat.district else '其他'
            town = stat.id.get('town')
            daily_code = stat.id.get('daily_code')

            _row = district_map.get(town if town else '其他') - 1
            sheet.write_string(_row, 2, town)
            sheet.write_string(_row, 1, district)
            ad_district = AdministrativeDivision.sync_find_one({'title': district})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_district.code})
            for _c in _county:
                county_map[_c] = district

            sheet.write_string(_row, daily_map.get(daily_code), str(stat.sum))
            sheet.write_string(_row, 0, "六安市")
            if _row > _max_row:
                _max_row = _row
            v_list.append(stat.sum)
        except StopIteration:
            break
        except Exception as e:
            print(e)

    for k, v in county_map.items():
        if k not in district_map:
            _max_row += 1
            sheet.write_string(_max_row, 1, v)
            sheet.write_string(_max_row, 2, k)
            sheet.write_string(_max_row, 0, "六安市")
    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def get_region_match(race):
    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    return {'city': {'$in': city_name_list}, 'district': {'$in': dist_list}}


def export_race_member_base_information(prov_match, city_match, workbook, match, title, district_title_list,
                                        prov_race_cid, city_race_cid):
    """
    导出参与人数，通关人数，正确率top100的个人信息(手机号码)
    :param workbook:
    :return:
    """
    sheet = workbook.add_worksheet("{title}会员信息统计".format(title=title))
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
    sheet = generate_excel_head(sheet, data_center_format)

    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    # district_lookup_stage = LookupStage(AdministrativeDivision, 'district_code', 'post_code', 'district_list')
    add_fields_stage = AddFieldsStage(t_accuracy={
        '$cond':
            {
                'if': {'$eq': ['$total_count', 0]},
                'then': 0,
                'else':
                    {
                        '$divide': ['$total_correct', '$total_count']
                    }
            }
    })
    sort_stage = SortStage([('t_accuracy', DESC)])
    prov_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(prov_match), lookup_stage, add_fields_stage,
         MatchStage({'member_list': {"$ne": []}}), sort_stage], allowDiskUse=True)
    num = 1
    # total_member_list = []
    sheet.write_string(0, 6, '单位')
    while True:
        try:
            race_mapping = prov_race_mapping_cursor.next()
            if race_mapping:
                if race_mapping.member_list and race_mapping.auth_address.get('district'):
                    member = race_mapping.member_list[0]
                    # if member.cid not in total_member_list:
                    #     total_member_list.append(member.cid)
                    # if race_mapping.auth_address.get('district') in district_title_list:
                    sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                    sheet.write_string(num, 2, race_mapping.auth_address.get('district'), data_center_format)
                    sheet.merge_range(num, 3, num, 4, str(race_mapping.mobile), data_center_format)
                    sheet.write_number(num, 5, round(race_mapping.t_accuracy, 2), data_center_format)
                    if race_mapping.company_cid:
                        company = Company.sync_find_one({'cid': race_mapping.company_cid})
                        if company:
                            sheet.write_string(num, 6, company.title)
                    num += 1
                    # else:
                    #     continue
            else:
                continue
        except StopIteration:
            break
    city_match = {'race_cid': city_race_cid,
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': '六安市', "record_flag": 1, "auth_address.district": {'$in': district_title_list},
                  }
    city_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(city_match), lookup_stage, add_fields_stage,
         MatchStage({'member_list': {"$ne": []}}), sort_stage], allowDiskUse=True)
    #  六安市
    while True:
        try:
            race_mapping = city_race_mapping_cursor.next()
            if race_mapping:
                if race_mapping.member_list and race_mapping.auth_address.get('district'):
                    member = race_mapping.member_list[0]
                    # if member.cid not in total_member_list:
                    #     total_member_list.append(member.cid)
                    # if race_mapping.auth_address.get('district') in district_title_list:
                    sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                    sheet.write_string(num, 2, race_mapping.auth_address.get('district'), data_center_format)
                    sheet.merge_range(num, 3, num, 4, str(race_mapping.mobile), data_center_format)
                    sheet.write_number(num, 5, round(race_mapping.t_accuracy, 2), data_center_format)
                    if race_mapping.company_cid:
                        company = Company.sync_find_one({'cid': race_mapping.company_cid})
                        if company:
                            sheet.write_string(num, 6, company.title)
                    num += 1
                    # else:
                    #     continue
            else:
                continue
        except StopIteration:
            break
    #  安徽省六安市的最后一关关卡
    prov_last_checkpoint_cid, _, _, _ = get_export_param(prov_race_cid)
    print(prov_last_checkpoint_cid, '12')
    #  六安市活动的最后一关关卡
    city_last_checkpoint_cid, _, _, _ = get_export_param(city_race_cid)
    print(city_last_checkpoint_cid, '33')
    pass_sheet = workbook.add_worksheet("{title}通关会员信息统计".format(title=title))
    pass_sheet = generate_excel_head(pass_sheet, data_center_format)
    check_point_lookup = LookupStage(
        MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
        as_list_name='history_list',
        pipeline=[
            {
                '$match': {

                    '$expr': {
                        '$and': [
                            {'$eq': ['$member_cid', '$$primary_cid']},
                            {'$eq': ['$status', 1]},
                            {'$eq': ['$check_point_cid', prov_last_checkpoint_cid]}
                        ]
                    }

                }
            },
        ]
    )
    add_fields_stage = AddFieldsStage(t_accuracy={
        '$cond':
            {
                'if': {'$eq': ['$total_count', 0]},
                'then': 0,
                'else':
                    {
                        '$divide': ['$total_correct', '$total_count']
                    }
            }
    })
    city_check_point_lookup = LookupStage(
        MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
        as_list_name='history_list',
        pipeline=[
            {
                '$match': {

                    '$expr': {
                        '$and': [
                            {'$eq': ['$member_cid', '$$primary_cid']},
                            {'$eq': ['$status', 1]},
                            {'$eq': ['$check_point_cid', city_last_checkpoint_cid]}
                        ]
                    }

                }
            },
        ]
    )
    match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
    pass_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(prov_match), check_point_lookup, match_checkpoint_stage, lookup_stage, add_fields_stage], allowDiskUse=True)
    city_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(city_match), city_check_point_lookup, match_checkpoint_stage, lookup_stage, add_fields_stage], allowDiskUse=True)
    position = 1
    _total_pass_list = []
    pass_sheet.write(0, 6, '单位')
    while True:
        try:
            pass_race_mapping = pass_race_mapping_cursor.next()
            if pass_race_mapping:
                if pass_race_mapping.member_list:
                    member = pass_race_mapping.member_list[0]
                    if member.cid not in _total_pass_list:
                        _total_pass_list.append(member.cid)
                    else:
                        continue
                    # prov_sign = member.nick_name + pass_race_mapping.auth_address.get('district')
                    # if prov_sign not in prov_sign_list:
                    #     prov_sign_list.append(prov_sign)
                    # else:
                    #     continue
                    if pass_race_mapping.auth_address.get(
                            'district') in district_title_list and pass_race_mapping.auth_address.get('city') == "六安市":
                        pass_sheet.merge_range(position, 0, position, 1, member.nick_name, data_center_format)
                        pass_sheet.write_string(position, 2, pass_race_mapping.auth_address.get('district'),
                                                data_center_format)
                        pass_sheet.merge_range(position, 3, position, 4, str(pass_race_mapping.mobile),
                                               data_center_format)
                        pass_sheet.write_number(position, 5, round(pass_race_mapping.t_accuracy, 2),
                                                data_center_format)
                        if pass_race_mapping.company_cid:
                            company = Company.sync_find_one({'cid': pass_race_mapping.company_cid})
                            if company:
                                pass_sheet.write_string(position, 6, company.title)
                        position += 1
            else:
                continue
        except StopIteration:
            break
    while True:
        try:
            city_pass_race_mapping = city_race_mapping_cursor.next()
            if city_pass_race_mapping:
                if city_pass_race_mapping.member_list:
                    member = city_pass_race_mapping.member_list[0]
                    if member.cid not in _total_pass_list:
                        _total_pass_list.append(member.cid)
                    else:
                        continue
                    if city_pass_race_mapping.auth_address.get(
                            'district') in district_title_list and city_pass_race_mapping.auth_address.get(
                            'city') == "六安市":
                        pass_sheet.merge_range(position, 0, position, 1, member.nick_name, data_center_format)
                        pass_sheet.write_string(position, 2, city_pass_race_mapping.auth_address.get('district'),
                                                data_center_format)
                        pass_sheet.merge_range(position, 3, position, 4, str(city_pass_race_mapping.mobile),
                                               data_center_format)
                        pass_sheet.write_number(position, 5, round(city_pass_race_mapping.t_accuracy, 2),
                                                data_center_format)
                        if city_pass_race_mapping.company_cid:
                            company = Company.sync_find_one({'cid': city_pass_race_mapping.company_cid})
                            if company:
                                pass_sheet.write_string(position, 6, company.title)
                        position += 1
            else:
                continue
        except StopIteration:
            break
    print("information calc end ------------------")


def generate_excel_head(sheet, character_format):
    """
    生成excel表头信息
    :param sheet:
    :param character_format:
    :return:
    """
    sheet.merge_range(0, 0, 0, 1, '昵称', character_format)
    sheet.write_string(0, 2, '地区', character_format)
    sheet.merge_range(0, 3, 0, 4, '手机号码', character_format)
    sheet.write_string(0, 5, "正确率", character_format)
    return sheet


def district_belong_to_city(name):
    """
    得到某个市下面得所有地区
    :param name:
    :return:
    """
    city = AdministrativeDivision.sync_find_one({'title': name})
    district_title_list = AdministrativeDivision.sync_distinct("title", {"parent_code": city.code})
    return district_title_list


# def make_data(race_cid):
#     # company_list = Company.sync_find({'race_cid': race_cid, 'record_flag': 1}).to_list(None)
#     # cid_list = [company.cid for company in company_list]
#     # if company_list:
#     print('123')
#     mapping_list = RaceMapping.sync_find({'race_cid': race_cid, 'record_flag': 1, 'auth_address.town': {'$ne': None}}).to_list(None)
#     for mapping in mapping_list:
#         mapping.auth_address['town'] = None
#         mapping.sync_save()


def convert(num: int = 0):
    _map = {i: chr(ord('A') + i) for i in range(26)}
    if num == 0:
        return _map[num]

    ret_list = list()
    while True:
        if num == 0:
            break
        num, y = divmod(num, 26)
        ret_list.append(y)

    ret_list.reverse()
    temp_list = [r - 1 for r in ret_list[0:-1]]
    temp_list.append(ret_list[-1])
    return ''.join(map(lambda x: _map[x], temp_list))


def daily_people_liuan_anhui(workbook, match, sheet_name="每日新增参与人次"):
    """
    安徽活动，六安市每日参与的人次
    :param workbook:
    :param match
    :param sheet_name:
    :return:
    """
    city_count_match = {'race_cid': "CA755167DEA9AA89650D11C10FAA5413",
                        "city": "六安市",
                        'district': {'$in': district_title_list}}
    has_town_count_match = {'race_cid': "CA755167DEA9AA89650D11C10FAA5413",
                            "city": "六安市",
                            'district': {'$in': district_title_list},
                            "town": {'$ne': None}}
    no_town_count_match = {'race_cid': "CA755167DEA9AA89650D11C10FAA5413",
                            "city": "六安市",
                            'district': {'$in': district_title_list},
                            "town": {'$eq': None}}
    match_stage = MatchStage(match)
    group_stage = GroupStage(
        {'daily_code': '$daily_code', 'province': '$province', 'city': '$city', "district": "$district",
         'town': '$town'}, sum={'$sum': '$total_num'})
    sort_stage = SortStage([('_id.daily_code', ASC)])
    sheet = workbook.add_worksheet(sheet_name)
    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    sheet.write_string(0, 2, '总数')
    sheet.write_string(0, 3, '乡镇')

    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', city_count_match)
    print(daily_list, 'daily_list')
    daily_list.sort()
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 4, daily_code)
        daily_map[daily_code] = index + 4

    address_group = GroupStage({'province': '$province', 'city': '$city', "district": "$district", 'town': '$town'},
                               sum={'$sum': '$total_num'})
    address_sort = SortStage([('_id.district', ASC), ('_id.town', ASC)])
    city_address_list = ReportRacePeopleStatistics.sync_aggregate([MatchStage(has_town_count_match), address_group, address_sort], allowDiskUse=True)
    address_map = {}
    print(address_map, "address_map")
    district_dict = {}
    num = 1
    for index, address in enumerate(city_address_list):
        # city = address.id.get('city')
        district = address.id.get('district')
        if district not in district_dict:
            district_dict[district] = index + 1
        sheet.write_string(index + 1, 0, "六安市")
        town = address.id.get('town')
        # if not town:
        #     continue
        sheet.write_string(index + 1, 1, district)
        sheet.write_string(index + 1, 3, town)
        address_map[town] = index + 1
        num += 1
    print(district_dict, 'dict3')
    city_group = GroupStage({'daily_code': '$daily_code', 'city': '$city', 'district': '$district', 'town': '$town'},
               sum={'$sum': "$total_num"})
    print(address_map, 'add_map2')
    print(num, 'num1')
    #  六安有乡镇信息的数据
    has_town_cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(has_town_count_match), city_group], allowDiskUse=True)
    prov_cursor = ReportRacePeopleStatistics.sync_aggregate([match_stage, city_group], allowDiskUse=True)
    no_town_cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(no_town_count_match), city_group], allowDiskUse=True)
    no_town_city_map = {}
    prov_map = {}
    district_list = []
    prov_dis_list = []
    town_list = []
    #  安徽省的
    while True:
        try:
            stat = prov_cursor.next()
            district = stat.id.get('district')
            prov_dis_list.append(district)
            if district:
                if district not in prov_map:
                    prov_map[district] = stat.sum
                else:
                    prov_map[district] += stat.sum
        except StopIteration:
            break
        except Exception as e:
            raise e
    print(prov_map, 'prov_map2')
    #  六安市没有填乡镇的
    while True:
        try:
            stat = no_town_cursor.next()
            district = stat.id.get('district')
            prov_dis_list.append(district)
            if district:
                if district not in no_town_city_map:
                    no_town_city_map[district] = stat.sum
                else:
                    no_town_city_map[district] += stat.sum
        except StopIteration:
            break
        except Exception as e:
            raise e
    print(no_town_city_map, 'no_town_map')
    city_map = {}
    _dis_mapping = {}
    while True:
        try:
            stat = has_town_cursor.next()
            city = stat.id.get('city')
            district = stat.id.get('district')
            town = stat.id.get('town')
            if district not in _dis_mapping:
                _dis_mapping[district] = [town]
            else:
                _dis_mapping[district] += [town]
            # if not town:
            #     continue
            daily_code = stat.id.get('daily_code')
            town_list.append(town)
            _row = address_map.get(town)
            _col = daily_map.get(daily_code)
            print('%s - %s - %s - %s - %s - %s - %s' % (_row, _col, city, district, town, daily_code, stat.sum))
            sheet.write_number(_row, _col, stat.sum)
            _town = AdministrativeDivision.sync_find_one({'record_flag': 1, 'title': town, "level": "T"})
            if _town:
                _district = AdministrativeDivision.sync_find_one({'record_flag': 1, 'code': _town.parent_code})
                district_list.append(_district.title)
                if _district.title in district_list:
                    if _district.title not in city_map:
                        city_map[_district.title] = stat.sum
                    else:
                        city_map[_district.title] += stat.sum
                else:
                    district_list.append(_district)
            elif not _town and town == "顺和镇":
                _district = "裕安区"
                district_list.append(_district)
                if _district in district_list:
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
                else:
                    district_list.append(_district)
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
            elif not _town and town in ['教育系统',
                                         '人民路小学',
                                         '三里桥小学',
                                         '皖西路小学',
                                         '梅山路小学',
                                         '清水河学校',
                                         '金安路学校',
                                         '人民路小学东校',
                                         '区卫健委',
                                         '市第四人民医院',
                                         '区妇幼保健院',
                                         '区疾控中心',
                                         '区卫生监督所',
                                         '区妇幼保健计划生育服务中心'
                                         ]:
                _district = "金安区"
                district_list.append(_district)
                if _district in district_list:
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
                else:
                    district_list.append(_district)
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
            else:
                _district = "未知"
                district_list.append(_district)
                if _district in district_list:
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
                else:
                    district_list.append(_district)
                    if _district not in city_map:
                        city_map[_district] = stat.sum
                    else:
                        city_map[_district] += stat.sum
            # if _row > _max_row:
            #     _max_row = _row
        except StopIteration:
            break
        except Exception as e:
            raise e
    print(city_map, 'map3')
    count_total_mapping = {}
    for k, v in city_map.items():
        if k not in count_total_mapping:
            count_total_mapping[k] = v
        else:
            count_total_mapping[k] += v
    for k, v in prov_map.items():
        if k not in count_total_mapping:
            count_total_mapping[k] = v
        else:
            count_total_mapping[k] += v
    for k, v in no_town_city_map.items():
        if k not in count_total_mapping:
            count_total_mapping[k] = v
        else:
            count_total_mapping[k] += v
    print(count_total_mapping, 'total_mp')
    # for k, v in count_total_mapping.items():
    #     _row = district_dict.get(k)
        # sheet.write_number(_row, 2, v)
    print(district_dict, 'dis_di2')
    print(count_total_mapping, 'couont_ma[')
    print(sum(list(count_total_mapping.values())))
    total_key = list(count_total_mapping.keys())
    has_town_key = list(district_dict.keys())
    extra_key = list(set(total_key) - set(has_town_key))
    print(extra_key)
    district_map = get_all_district_town_map()
    print(num, 'num')
    for i in extra_key:
        sheet.write_string(num, 1, i)
        sheet.write_string(num, 0, "六安市")
        sheet.write_number(num, 2, count_total_mapping[i])
        v = district_map.get(i)
        if v:
            for index, title in enumerate(v):
                sheet.write_string(num, 3, title)
                sheet.write_string(num, 1, i)
                sheet.write_string(num, 0, '六安市')
                num += 1
        else:
            num += 1
        if i != "未知":
            del district_map[i]
        district_dict[i] = num
    for k, v in count_total_mapping.items():
        _row = district_dict.get(k)
        sheet.write_number(_row, 2, v)
    total_town_list = []
    print(town_list, 'to222')
    # for k, v in district_map.items():
    #     for title in enumerate(v):
    #         if title not in total_town_list:
    #             total_town_list.append(title)
    # print(len(total_town_list))
    # extra_town_list = list(set(total_town_list) - set(town_list))
    # print(len(extra_town_list), 'tol2')
    print(_dis_mapping, '_dis')
    for k, v in _dis_mapping.items():
        if k in district_map:
            a = list(set(district_map[k]) - set(_dis_mapping[k]))
            district_map[k] = a
    n = 0
    for k, v in district_map.items():
        n += len(v)
    print(n)
    print(num, 'last_num')
    for k, v in district_map.items():
        for index, title in enumerate(v):
            sheet.write_string(num, 0, "六安")
            sheet.write_string(num, 1, k)
            sheet.write_string(num, 3, title)
            num += 1
    #  没有答过题目得乡镇
    # for index, title in extra_town_list:
    #     sheet.write_string(num + index, 3, title)
    #     sheet.write_string(num + index, 0, "六安市")

    # district_map = get_all_district_town_map()

    # cursor = ReportRacePeopleStatistics.sync_aggregate([match_stage, group_stage, sort_stage])
    # _max_row = 0
    # while True:
    #     try:
    #         stat = cursor.next()
    #         city = stat.id.get('city')
    #         district = stat.id.get('district')
    #         town = stat.id.get('town')
    #         if not town:
    #             continue
    #         daily_code = stat.id.get('daily_code')
    #         _row = address_map.get(town)
    #         _col = daily_map.get(daily_code)
    #         print('%s - %s - %s - %s - %s - %s - %s' % (_row, _col, city, district, town, daily_code, stat.sum))
    #         sheet.write_number(_row, _col, stat.sum)
    #
    #         if _row > _max_row:
    #             _max_row = _row
    #     except StopIteration:
    #         break
    #     except Exception as e:
    #         raise e
    #
    # sheet.write_string(_max_row + 1, 0, '总和')
    # total_start = convert(len(daily_list) + 2) + "2"
    # print(total_start, 'start1')
    # total_end = convert(len(daily_list) + 2) + str(_max_row + 1)
    # print(total_end, 'start2')
    # total_formula = "=SUM(" + total_start + ":" + total_end + ")"
    # sheet.write_formula(_max_row + 1, 1, total_formula)
    # count = len(daily_list) + 2
    sheet.write_string(0, len(daily_list) + 4, "合计")
    for i in range(2, num + 1):
        start = convert(4)
        start = start + str(i)
        end = convert(len(daily_list) + 3)
        end = end + str(i)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(i - 1, len(daily_list) + 4, formula)
    sheet.write_string(num, 0, "总计")
    sheet.write_number(num, 1, sum(count_total_mapping.values()))


def daily_code_company_count(book, match, city_race_cid, sheet_name="单位每日参与人次"):
    """
    每日单位参与人次
    :param book:
    :param match
    :param sheet_name:
    :return:
    """
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'company_cid': "$company_cid",
             "member_list": "$member_list",
             "member_cid": "$member_cid",
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'company_cid': '$company_cid'}, sum={'$sum': 1},
                    cid_list={'$push': '$member_cid'}),

         SortStage([('_id.daily_code', ASC)])],allowDiskUse=True)
    sheet.write_string(0, 0, "单位")
    daily_list = []
    prize_list = []
    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None
            company_cid = data.id.get('company_cid')
            if company_cid is None:
                continue
            else:
                company = Company.sync_get_by_cid(company_cid)
                title = company.title
            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, title)
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1
            enter_count = 0
            race_cid = city_race_cid
            check_point_cid_list = RaceGameCheckPoint.sync_distinct("cid", {'race_cid': race_cid, 'record_flag': 1})
            if data.cid_list:
                for cid in data.cid_list:
                    if daily_code != "未知":
                        date = transform_date(daily_code)
                        tomorrow = date + datetime.timedelta(days=1)
                        checkpoint_history_list = MemberCheckPointHistory.sync_find(
                            {'created_dt': {'$gte': date, "$lte": tomorrow}, "member_cid": cid,
                             'check_point_cid': {'$in': check_point_cid_list}}).to_list(None)
                        enter_count += len(checkpoint_history_list)
            sheet.write_number(_current_row, _current_col, enter_count)

            v_list.append(enter_count)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e
    print(prize_list, 'list1')
    print(len(prize_list))
    print(_max_row)
    company = Company.sync_distinct('title', {'race_cid': "CA755167DEA9AA89650D11C10FAA5413"})
    extra_company = list(set(company) - set(prize_list))
    print(extra_company)
    for i in extra_company:
        sheet.write_string(_max_row + 1, 0, i)
        _max_row += 1
    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))
    count = len(daily_list) + 1
    sheet.write_string(0, count, "合计")
    for i in range(2, _max_row + 2):
        start = convert(1)
        start = start + str(i)
        end = convert(len(daily_list))
        end = end + str(i)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(i - 1, len(daily_list) + 1, formula)


def transform_date(time_str):
    """
    将时间字符串转换成日期 20190627转换成Date(20190627)
    :param time_str:
    :return:
    """
    date = time_str[:4] + '/' + time_str[4:6] + '/' + time_str[6:]
    date = date.replace("/0", "/")
    return str2datetime(date, "%Y/%m/%d")


def people_count(prov_race_cid, city_race_cid, workbook, sheet_name="每日新增参与人次"):
    """
    从历史表(Member_check_point_history)中统计参与人次
    :param prov_race_cid:
    :param city_race_cid:
    :param pre_match
    :return:
    """
    # 区及对应的乡镇
    # district_map = {}
    # district_list = AdministrativeDivision.sync_find({'parent_code': "341500"}).to_list(None)
    # for index, district in enumerate(district_list):
    #     town_list = AdministrativeDivision.sync_find({'parent_code': district.code}).to_list(None)
    #     district_map[district.title] = [town.title for town in town_list]
    # print("原始区信息")
    # print(district_map)
    district_map = get_all_district_town_map()
    pro_check_point = RaceGameCheckPoint.sync_find({"race_cid": prov_race_cid}).to_list(None)
    city_check_point = RaceGameCheckPoint.sync_find({"race_cid": city_race_cid}).to_list(None)
    pro_check_point_cids = [point.cid for point in pro_check_point]
    city_check_point_cids = [point.cid for point in city_check_point]
    # 安徽
    prov_match = MatchStage({"race_cid": prov_race_cid, "auth_address.city": '六安市'})
    prov_project = ProjectStage(
        **{'city': "$auth_address.city", 'district': "$auth_address.district", "member_cid": "$member_cid"})
    prov_group = GroupStage({'city': '$city', "district": "$district"}, member_list={'$push': '$member_cid'})
    prov_members_from_race_mapping = RaceMapping.sync_aggregate([prov_match, prov_project, prov_group], allowDiskUse=True).to_list(None)
    district_total_map = {}  # 区域-总人次
    for prov_race_mapping in prov_members_from_race_mapping:
        prov_district = prov_race_mapping.id.get('district')
        print(prov_district)
        if prov_district is None:
            continue
        prov_member_count = MemberCheckPointHistory.sync_count(
            {'member_cid': {'$in': prov_race_mapping.member_list}, 'check_point_cid': {'$in': pro_check_point_cids}})
        district_total_map[prov_district] = prov_member_count
    print("-----------安徽区域人次------------------")
    print(district_total_map)
    # 六安人次统计
    city_match = MatchStage({"race_cid": city_race_cid, "auth_address.town": {'$ne': None}})
    project = ProjectStage(**{'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
                              'city': "$auth_address.city", 'district': "$auth_address.district",
                              'town': "$auth_address.town", "member_cid": "$member_cid"})
    group = GroupStage({'daily_code': '$daily_code', 'province': '$province', 'city': '$city', "district": "$district",
                        'town': '$town'}, member_list={'$push': '$member_cid'})
    city_members_from_race_mapping = RaceMapping.sync_aggregate([city_match, project, group], allowDiskUse=True).to_list(None)

    daily_list = []  # 所有日期,excel横轴
    count_list = []  # (town,daily_code,人次)
    for index, race_mapping in enumerate(city_members_from_race_mapping):
        daily_code = race_mapping.id.get('daily_code')
        city = race_mapping.id.get('city')
        district = race_mapping.id.get('district')
        town = race_mapping.id.get('town')
        if daily_code:
            if daily_code not in daily_list:
                daily_list.append(daily_code)
            if town is not None:
                # if town not in district_map[district]:
                #     print("需添加的Town",daily_code,city,district,town)
                #     district_map[district].append(town)
                # print("跳过")
                # continue
                member_histories = MemberCheckPointHistory.sync_aggregate([
                    ProjectStage(**{'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
                                    'member_cid': '$member_cid', 'check_point_cid': '$check_point_cid'}),
                    MatchStage({'member_cid': {'$in': race_mapping.member_list},
                                'check_point_cid': {'$in': city_check_point_cids}, 'daily_code': daily_code})
                ], allowDiskUse=True).to_list(None)
                # 乡镇参与人次
                town_total = len(member_histories)
                if district:
                    if district in district_total_map.keys():
                        district_total_map[district] += town_total
                    else:
                        district_total_map[district] = town_total
                print("***", daily_code, city, district, town)
                print(district_total_map[district])
                key = '{}-{}'.format(district, town)
                count_list.append((key, daily_code, len(member_histories)))

    print("区信息")
    print(district_map, 'disss_mapping')
    daily_list.sort()
    print("-------------------")
    print("日期")
    print(daily_list)
    print("六安乡镇人次")
    print(count_list)
    print("合并人次")
    print(district_total_map)

    sheet = workbook.add_worksheet(sheet_name)
    # excel行名
    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    sheet.write_string(0, 2, '总数')
    sheet.write_string(0, 3, '乡镇')
    daily_map = {}  # 保存日期所在的列号
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 4, daily_code)
        daily_map[daily_code] = index + 4
    print("-------日期-行号-----------")
    print(daily_map)
    # excel列名输出,并记录各区所在行号，个乡镇所在行号
    district_row = {}
    town_row = {}
    _current_row = 1
    count = 0
    for district, town_list in district_map.items():
        for index, town in enumerate(town_list):
            if index == 0:
                district_row[district] = _current_row
            key = '{}-{}'.format(district, town)
            town_row[key] = _current_row
            sheet.write_string(_current_row, 0, "六安市")
            sheet.write_string(_current_row, 1, district)
            sheet.write_string(_current_row, 3, town)
            _current_row += 1
            count += 1

    print("-----区域-行号-----")
    print(district_row)
    print("-----乡镇-行号-----")
    print(town_row)
    # excel输出区域总人次
    for district, district_total in district_total_map.items():
        print('%s 所属行号: %s 数量 %s' % (district, district_row[district], district_total))
        sheet.write_number(district_row[district], 2, district_total)
    # excel输出乡镇参与人次
    for count in count_list:
        town = count[0]
        if town in town_row.keys():
            row = town_row[count[0]]
            col = daily_map[count[1]]
        else:
            continue
        print('%s - %s 所在行:%s,列:%s 数量：%s' % (count[0], count[1], row, col, count[2]))
        sheet.write_number(row, col, count[2])
    # excel合计
    print(_current_row + 1)
    _max_col = len(daily_list) + 4
    print(len(daily_list))
    _max_col_name = convert(_max_col - 1)
    # 区域总和
    sheet.write_string(_current_row, 1, '总和')
    start = "C1"
    end = "C" + str(_current_row)
    formula = "=SUM(" + start + ":" + end + ")"
    sheet.write_formula(_current_row, 2, formula)
    # 各乡镇总和
    sheet.write_string(0, _max_col, "合计")
    for i in range(2, _current_row + 1):
        start = "E" + str(i)
        end = _max_col_name + str(i)
        formula = "=SUM(" + start + ":" + end + ")"
        sheet.write_formula(i - 1, _max_col, formula)
        print(formula)
    print(count, 'count123')


def get_all_district_town_map():
    """
    得到区域和乡镇的对应关系
    :return:
    """
    district_map = {}
    district_list = AdministrativeDivision.sync_find({'parent_code': "341500"}).to_list(None)
    for index, district in enumerate(district_list):
        town_list = AdministrativeDivision.sync_find({'parent_code': district.code}).to_list(None)
        district_map[district.title] = [town.title for town in town_list]
    district_map['金安区'] += ['教育系统',
                            '人民路小学',
                            '三里桥小学',
                            '皖西路小学',
                            '梅山路小学',
                            '清水河学校',
                            '金安路学校',
                            '人民路小学东校',
                            '区卫健委',
                            '市第四人民医院',
                            '区妇幼保健院',
                            '区疾控中心',
                            '区卫生监督所',
                            '区妇幼保健计划生育服务中心'
                            ]
    return district_map


if __name__ == '__main__':
    # make_data()
     export_town_member_information("CA755167DEA9AA89650D11C10FAA5413", "3040737C97F7C7669B04BC39A660065D")
    # a = get_all_district_town_map()
    # print(a, '123')
    # a = transform_date("20190527")
    # print(a)
    # district_map = get_all_district_town_map()
    # count = 0
    # for district, town_list in district_map.items():
    #     for index, town in enumerate(town_list):
    #         count += 1
    # print(count)
    # print(district_map)
    # print(district_map["金安区"])
    # # print(district_map['霍邱县'])
    # # # print(len(district_map.keys()))
    # num = 0
    # special_list = ['教育系统',
    #                 '人民路小学',
    #                 '三里桥小学',
    #                 '皖西路小学',
    #                 '梅山路小学',
    #                 '清水河学校',
    #                 '金安路学校',
    #                 '人民路小学东校',
    #                 '区卫健委',
    #                 '市第四人民医院',
    #                 '区妇幼保健院',
    #                 '区疾控中心',
    #                 '区卫生监督所',
    #                 '区妇幼保健计划生育服务中心'
    #                 ]
    # for k, v in district_map.items():
    #     num += len(v)
    # print(num, '123')
    # make_data("3040737C97F7C7669B04BC39A660065D")
    #  onlline liuan  CA755167DEA9AA89650D11C10FAA5413
    #  local  0456603A25199D2B543C9A1B53B99666
