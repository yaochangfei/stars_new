import datetime

import xlsxwriter

from db.models import RaceMapping, MemberCheckPointHistory, RaceGameCheckPoint, ReportRacePeopleStatistics, Race, \
    AdministrativeDivision, Member
from motorengine import DESC
from motorengine.stages import LookupStage, MatchStage, GroupStage, SortStage
from motorengine.stages.add_fields_stage import AddFieldsStage

now = format(datetime.datetime.now(), "%Y-%m-%d %H:%M")


def export_race_enter_data(race_cid: str, last_checkpoint_cid, title, district_title_list):
    """
    导入活动下面的参与人数， 参与人次，通关人数
    :param race_cid:
    :return:
    """
    print('start --------------')
    if not isinstance(race_cid, str):
        raise ValueError("race_cid is not str type")
    race = Race.sync_find_one({'cid': race_cid, 'record_flag': 1})
    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    match = MatchStage({'race_cid': race_cid, 'record_flag': 1})
    race_mapping_list = RaceMapping.sync_aggregate(stage_list=[match, lookup_stage, MatchStage({'member_list': {'$ne': []}})]).to_list(None)
    if not race_mapping_list:
        print('该活动下面没有人参与!')
        return
    #  参与人数
    enter_quantity = len(race_mapping_list)
    print(enter_quantity, 'quantity')
    #  参与人次
    cursor = ReportRacePeopleStatistics.sync_aggregate([
        MatchStage({'race_cid': race_cid, 'province': {'$ne': None}, 'city': {"$in": city_name_list},
                    'district': {"$in": dist_list}}),
        GroupStage("city", sum={'$sum': '$total_num'})
    ])
    enter_count = 0
    while True:
        try:
            pass_people = cursor.next()
            if pass_people:
                enter_count += pass_people.sum
        except StopIteration:
            break
        except Exception as e:
            print(e)
    # 通关人数
    match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1})
    check_point_lookup = LookupStage(
        MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
        as_list_name='history_list',
        pipeline=[
            {'$match': {
                '$expr': {
                    '$and': [
                        {'$eq': ['$member_cid', '$$primary_cid']},
                        {'$eq': ['$status', 1]},
                        {'$eq': ['$check_point_cid', last_checkpoint_cid]}
                    ]
                }

            }
            },
        ]

    )
    match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    district_lookup_stage = LookupStage(AdministrativeDivision, 'district_code', 'post_code', 'district_list')
    stats = RaceMapping.sync_aggregate(
        stage_list=[match_stage, check_point_lookup, match_checkpoint_stage, lookup_stage, district_lookup_stage])
    pass_num = 0
    while True:
        try:
            pass_race_mapping = stats.next()
            if pass_race_mapping:
                if pass_race_mapping.member_list and pass_race_mapping.district_list:
                    district = pass_race_mapping.district_list[0]
                    if district.title in district_title_list:
                        pass_num += 1
            else:
                continue
        except StopIteration:
            break
    excel_title = "{name}活动统计{time}.xlsx".format(name=title, time=now)
    title = "{name}信息统计".format(name=title)
    workbook = xlsxwriter.Workbook(excel_title)
    sheet = workbook.add_worksheet(title)
    sheet.write_string(0, 0, '参与人数')
    sheet.write_string(0, 1, '参与人次')
    sheet.write_string(0, 2, '通关人数')
    sheet.write_number(1, 0, enter_quantity)
    sheet.write_number(1, 1, enter_count)
    sheet.write_number(1, 2, pass_num)
    # workbook.close()
    print('end-------------------')


def export_race_enter_information(race_cid: str, last_checkpoint_cid, title, city_title_list, district_title_list):
    """
    导出参与人数，通关人数，正确率top100的个人信息(手机号码)
    :param race_cid:
    :return:
    """
    print("information calc start ------------------")
    if not race_cid or not isinstance(race_cid, str):
        raise ValueError("race_cid is empty or race_cid is not str")
    workbook = xlsxwriter.Workbook("{title}会员信息统计{time}.xlsx".format(title=title, time=now))
    sheet = workbook.add_worksheet("{title}会员信息统计".format(title=title))
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
    sheet = generate_excel_head(sheet, data_center_format)

    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    district_lookup_stage = LookupStage(AdministrativeDivision, 'district_code', 'post_code', 'district_list')
    match_stage = MatchStage({'race_cid': race_cid, 'record_flag': 1, 'auth_address.city': {'$in': city_title_list},
                              'auth_address.district': {'$in': district_title_list}})
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
    race_mapping_cursor = RaceMapping.sync_aggregate(
        [match_stage, lookup_stage, district_lookup_stage, add_fields_stage, sort_stage])
    num = 1
    #  正确率前100
    accuracy_top_sheet = workbook.add_worksheet("{title}会员正确率top100信息统计".format(title=title))
    accuracy_top_sheet = generate_excel_head(accuracy_top_sheet, data_center_format)
    while True:
        try:
            race_mapping = race_mapping_cursor.next()
            if race_mapping:
                if race_mapping.member_list and race_mapping.auth_address.get('district'):
                    member = race_mapping.member_list[0]
                    if race_mapping.auth_address.get('district') in district_title_list:
                        sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                        sheet.write_string(num, 2, race_mapping.auth_address.get('district'), data_center_format)
                        sheet.merge_range(num, 3, num, 4, str(race_mapping.mobile), data_center_format)
                        #  正确率前100
                        if num <= 100:
                            accuracy_top_sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                            accuracy_top_sheet.write_string(num, 2, race_mapping.auth_address.get('district'), data_center_format)
                            accuracy_top_sheet.merge_range(num, 3, num, 4, str(race_mapping.mobile), data_center_format)
                        num += 1
            else:
                continue
        except StopIteration:
            break
    print(num, '123')
    # 通关人数
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
                            {'$eq': ['$check_point_cid', last_checkpoint_cid]}
                        ]
                    }

                }
            },
        ]
    )
    match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
    pass_race_mapping_cursor2 = RaceMapping.sync_aggregate(
        [match_stage, check_point_lookup, match_checkpoint_stage, lookup_stage, district_lookup_stage]).to_list(None)
    print(len(pass_race_mapping_cursor2))
    pass_race_mapping_cursor = RaceMapping.sync_aggregate(
        [match_stage, check_point_lookup, match_checkpoint_stage, lookup_stage, district_lookup_stage])
    position = 1
    while True:
        try:
            pass_race_mapping = pass_race_mapping_cursor.next()
            if pass_race_mapping:
                if pass_race_mapping.member_list and pass_race_mapping.district_list:
                    member = pass_race_mapping.member_list[0]
                    district = pass_race_mapping.district_list[0]
                    if district.title in district_title_list:
                        pass_sheet.merge_range(position, 0, position, 1, member.nick_name, data_center_format)
                        pass_sheet.write_string(position, 2, district.title, data_center_format)
                        pass_sheet.merge_range(position, 3, position, 4, str(pass_race_mapping.mobile), data_center_format)
                        position += 1
            else:
                continue
        except StopIteration:
            break
    workbook.close()
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


def see_pass_count(check_point_cid):
    history_list = MemberCheckPointHistory.sync_distinct("member_cid", {'check_point_cid': check_point_cid, 'status': 1})
    print(len(history_list))
    mapping_list = RaceMapping.sync_count({'race_cid': '3040737C97F7C7669B04BC39A660065D'})
    print(mapping_list)
    member_list = RaceMapping.sync_distinct("member_cid", {'race_cid': '3040737C97F7C7669B04BC39A660065D'})
    print(len(member_list))


def get_export_param(race_cid):
    """
    得到竞赛导出数据参数
    :param race_cid:
    :return:
    """
    race = Race.sync_find_one({"cid": race_cid})
    checkpoint_list = RaceGameCheckPoint.sync_find({'race_cid': race_cid, 'record_flag': 1}).sort('index').to_list(None)
    #  该活动最后一卡的关卡cid
    last_checkpoint_cid = ''
    if checkpoint_list:
        last_checkpoint_cid = checkpoint_list[-1].cid
    if not race.city_code:
        prov = AdministrativeDivision.sync_find_one({'code': race.province_code})
        title = prov.title
        #  去除脏数据
        city_list = AdministrativeDivision.sync_find({'parent_code': prov.code}).to_list(None)
        city_title_list = [city.title for city in city_list]
        city_code_list = [city.code for city in city_list]
        district_title_list = AdministrativeDivision.sync_distinct("title", {'parent_code': {'$in': city_code_list}})
    else:
        city = AdministrativeDivision.sync_find_one({'code': race.city_code})
        city_title_list = [city.title]
        district_title_list = AdministrativeDivision.sync_distinct("title", {'parent_code': city.code})
        title = city.title
    return last_checkpoint_cid, title, city_title_list, district_title_list


if __name__ == '__main__':
    last_checkpoint_cid, title, city_title_list, district_title_list = get_export_param(
        "3040737C97F7C7669B04BC39A660065D")
    export_race_enter_data("3040737C97F7C7669B04BC39A660065D", last_checkpoint_cid, title, district_title_list)
    export_race_enter_information("3040737C97F7C7669B04BC39A660065D", last_checkpoint_cid, title, city_title_list, district_title_list)
    # see_pass_count("05528C744EE42E838F7EE9D69070E6AA")