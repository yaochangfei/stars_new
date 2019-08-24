# !/usr/bin/python
# -*- coding:utf-8 -*-
import json

from db.models import Race, RaceGameCheckPoint, MemberCheckPointHistory, RaceMapping
from pymongo import ReadPreference


def parse_condition(condition=None):
    """
    解析后台报表json字符串
    用于： 学习行为统计，分享行为统计，导入行为统计
    :param condition:
    :return:
    """
    if not condition:
        return {}
    cond_dict = json.loads(condition)
    match_dict = {}

    age = cond_dict.get('age_group_list')
    if age:
        match_dict['age_group'] = age[0]

    sex = cond_dict.get('gender_list')
    if sex:
        match_dict['sex'] = sex[0]

    region_match = []
    province_code_list = cond_dict.get('province_code_list', [])
    city_code_list = cond_dict.get('city_code_list', [])
    if city_code_list:
        region_match.append({'city_code': {'$in': city_code_list}})

    if province_code_list:
        region_match.append({'province_code': {'$in': province_code_list}})

    if region_match:
        match_dict['$or'] = region_match

    education_list = cond_dict.get('education_list')
    if education_list:
        match_dict['education'] = education_list[0]

    return match_dict


def parse_race_condition(condition=None):
    """
    解析活动报表和活动执行报表中参与人数 正确率统计
    :param condition:
    :return:
    """
    if not condition:
        return {}
    cond_dict = json.loads(condition)
    # dimension_list = cond_dict.get('dimension_list', [])
    match_dict = {}

    age = cond_dict.get('age_group_list')
    if age:
        match_dict['age_group'] = age[0]

    sex = cond_dict.get('gender_list')
    if sex:
        match_dict['sex'] = sex[0]
    #  重点人群
    important_crowd = cond_dict.get('important_people', [])
    if important_crowd:
        match_dict['category'] = important_crowd[0]
    education_list = cond_dict.get('education_list')
    if education_list:
        match_dict['education'] = education_list[0]
    # parent_cid_list = []
    # if dimension_list:
    #     for dimension in dimension_list:
    #         parent_cid = list(dimension.keys())[0]
    #         # print(parent_cid, 'cid')
    #
    #         # category_cid = list(dimension.values())[0]['cid']
    #
    # parent_cid_set = set(parent_cid_list)
    return match_dict


def parse_json_condition(condition=None):
    """
    解析json condition字符串，仅用于折线图图表导出模块
    :param condition:
    :return:
    """

    if not condition:
        return {}

    condition = json.loads(condition)
    return {cond_name: cond_dict.get('condition_value') for cond_name, cond_dict in condition.items()}


def adjust_race_report_accuracy(race_cid):
    """
    活动报表线上数据填充正确率数据
    :param race_cid:
    :return:
    """
    race = Race.sync_find_one({'cid': race_cid})
    if not race:
        print("活动不存在, 请检查！")
        return
    #  找到该活动下面所有的关卡
    check_point_cid_list = RaceGameCheckPoint.sync_distinct("cid", {'race_cid': race_cid})
    print(check_point_cid_list)
    if not check_point_cid_list:
        print("该活动下面没有关卡")
        return
    #  给race_mapping从历史记录统计正确率
    try:
        for check_point_cid in check_point_cid_list:
            check_point_history_list = MemberCheckPointHistory.sync_find({"check_point_cid": check_point_cid}).to_list(
                None)
            for check_point_history in check_point_history_list:
                race_mapping = RaceMapping.sync_find_one(
                    {'member_cid': check_point_history.member_cid, "race_cid": race_cid},
                    read_preference=ReadPreference.PRIMARY)
                race_mapping.total_count += len(check_point_history.result)
                num = 0
                for result in check_point_history.result:
                    if result.get("true_answer"):
                        num += 1
                race_mapping.total_correct += num
                race_mapping.sync_save()
    except Exception as e:
        print(str(e))


if __name__ == '__main__':
    adjust_race_report_accuracy("DF1EDC30F120AEE93351A005DC97B5C1")
    adjust_race_report_accuracy("F742E0C7CA5F7E175844478D74484C29")
    # pass
