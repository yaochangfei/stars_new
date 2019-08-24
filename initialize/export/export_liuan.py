import datetime

import xlsxwriter
from db.models import AdministrativeDivision
from db.models import Member, RaceMapping, Company, MemberCheckPointHistory
from initialize.export.export_race_people_information import get_export_param
from initialize.export.export_town_information import generate_excel_head
from motorengine import DESC
from motorengine.stages import LookupStage, SortStage, MatchStage
from motorengine.stages.add_fields_stage import AddFieldsStage

district_title_list = ['舒城县', '叶集区', '霍邱县', '金安区', '裕安区', '金寨县', '开发区', '霍山县']


def export_race_member_base_information(prov_match, title, district_title_list):
    """
    导出参与人数，通关人数，正确率top100的个人信息(手机号码)
    :param workbook:
    :return:
    """
    now = format(datetime.datetime.now(), "%Y-%m-%d%H:%M")
    excel_title = "六安市活动统计{time}.xlsx".format(time=now)
    workbook = xlsxwriter.Workbook(excel_title)
    sheet = workbook.add_worksheet("{title}会员信息统计".format(title=title))
    data_center_format = workbook.add_format(
        {'valign': 'vcenter', 'align': 'center', 'font_name': 'Microsoft YaHei', 'border': 1})
    # sheet = generate_excel_head(sheet, data_center_format)
    sheet.merge_range(0, 0, 0, 1, '昵称', data_center_format)
    sheet.write_string(0, 2, '城市', data_center_format)
    sheet.write_string(0, 3, '地区', data_center_format)
    sheet.merge_range(0, 4, 0, 5, '手机号码', data_center_format)
    sheet.write_string(0, 6, "正确率", data_center_format)
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
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
    prov_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(prov_match), lookup_stage, add_fields_stage,
         MatchStage({'member_list': {"$ne": []}})])
    num = 1
    # total_member_list = []
    sheet.write_string(0, 7, '单位/乡镇')
    while True:
        try:
            race_mapping = prov_race_mapping_cursor.next()
            if race_mapping:
                if race_mapping.member_list and race_mapping.auth_address.get('city') == "六安市" and race_mapping.auth_address.get('district') in district_title_list:
                    member = race_mapping.member_list[0]
                    # if member.cid not in total_member_list:
                    #     total_member_list.append(member.cid)
                    # if race_mapping.auth_address.get('district') in district_title_list:
                    sheet.merge_range(num, 0, num, 1, member.nick_name, data_center_format)
                    sheet.write_string(num, 2, race_mapping.auth_address.get('city'), data_center_format)
                    sheet.write_string(num, 3, race_mapping.auth_address.get('district'), data_center_format)
                    sheet.merge_range(num, 4, num, 5, str(race_mapping.mobile), data_center_format)
                    sheet.write_number(num, 6, round(race_mapping.t_accuracy, 2), data_center_format)
                    if race_mapping.company_cid:
                        company = Company.sync_find_one({'cid': race_mapping.company_cid})
                        if company:
                            sheet.write_string(num, 7, company.title)
                    elif race_mapping.auth_address.get('town'):
                        sheet.write_string(num, 7, race_mapping.auth_address.get('town'))
                    num += 1
            else:
                continue
        except StopIteration:
            break
    # 六安市的最后一关关卡
    city_last_checkpoint_cid, _, _, _ = get_export_param("CA755167DEA9AA89650D11C10FAA5413")
    print(city_last_checkpoint_cid)
    pass_sheet = workbook.add_worksheet("{title}通关会员信息统计".format(title=title))
    # pass_sheet = generate_excel_head(pass_sheet, data_center_format)
    pass_sheet.merge_range(0, 0, 0, 1, '昵称', data_center_format)
    pass_sheet.write_string(0, 2, '城市', data_center_format)
    pass_sheet.write_string(0, 3, '地区', data_center_format)
    pass_sheet.merge_range(0, 4, 0, 5, '手机号码', data_center_format)
    pass_sheet.write_string(0, 6, "正确率", data_center_format)
    pass_sheet.write_string(0, 7, "单位或乡镇", data_center_format)
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
                            {'$eq': ['$check_point_cid', city_last_checkpoint_cid]}
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
    match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
    pass_race_mapping_cursor = RaceMapping.sync_aggregate(
        [MatchStage(prov_match), check_point_lookup, match_checkpoint_stage, lookup_stage, add_fields_stage])
    position = 1
    _total_pass_list = []
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
                    if pass_race_mapping.auth_address.get(
                            'district') in district_title_list and pass_race_mapping.auth_address.get('city') == "六安市" and pass_race_mapping.auth_address.get('district') in district_title_list:
                        pass_sheet.merge_range(position, 0, position, 1, member.nick_name, data_center_format)
                        pass_sheet.write_string(position, 2, pass_race_mapping.auth_address.get('city'), data_center_format)
                        pass_sheet.write_string(position, 3, pass_race_mapping.auth_address.get('district'),
                                                data_center_format)
                        pass_sheet.merge_range(position, 4, position, 5, str(pass_race_mapping.mobile),
                                               data_center_format)
                        pass_sheet.write_number(position, 6, round(pass_race_mapping.t_accuracy, 2),
                                                data_center_format)
                        if pass_race_mapping.company_cid:
                            company = Company.sync_find_one({'cid': pass_race_mapping.company_cid})
                            if company:
                                pass_sheet.write_string(position, 7, company.title)
                        elif pass_race_mapping.auth_address.get('town'):
                            sheet.write_string(num, 7, pass_race_mapping.auth_address.get('town'))
                        position += 1
            else:
                continue
        except StopIteration:
            break

    print("information calc end ------------------")
    workbook.close()


if __name__ == '__main__':
    #  安徽得code 340000
    city_list = AdministrativeDivision.sync_find({"parent_code": "341500"}).to_list(None)
    city_name_list = [city.title for city in city_list]
    print(city_name_list)
    dis_list = []
    for city in city_list:
        district_list = AdministrativeDivision.sync_distinct("title", {"parent_code": city.code})
        for title in district_list:
            if title not in dis_list:
                dis_list.append(title)
    print(dis_list, '9999')
    prov_match = {'race_cid': "CA755167DEA9AA89650D11C10FAA5413",
                  "auth_address.province": {'$ne': None},
                  'auth_address.city': "六安市", "record_flag": 1, "auth_address.district": {'$in': city_name_list}}
    export_race_member_base_information(prov_match, title="六安市", district_title_list=city_name_list)

