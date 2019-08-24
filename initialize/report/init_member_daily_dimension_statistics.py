#! /usr/bin/python


import datetime
import traceback

from bson import ObjectId
from commons.common_utils import datetime2str
from db.models import Member, Subject, MemberDailyDimensionStatistics, MemberGameHistory
from initialize.init_member_property_statistics_data_v2 import complete_member_city_code
from pymongo import ReadPreference


def start_dashboard_report_statistics_without_delay(history):
    try:
        member = Member.sync_get_by_cid(history.member_cid)
        if not member:
            print('--- no member cid, history_cid=%s' % history.cid)
            return
        # START 自然日会员维度统计
        member_daily_dimension_statistics(history, member)
        # END 自然日会员维度统计

    except Exception:
        print(traceback.format_exc())


def member_daily_dimension_statistics(history, member: Member):
    result = {'code': 0}
    try:
        daily_code, result_list = _get_daily_code(history.fight_datetime), history.result if history.result else []
        insert_mdds_list = []
        for result in result_list:
            if result:
                subject_cid = result.get('subject_cid')
                if subject_cid:
                    subject = Subject.sync_get_by_cid(subject_cid)
                    if subject and subject.dimension_dict:
                        query = {'daily_code': daily_code, 'member_cid': member.cid}
                        query.update({'dimension.%s' % k: v for k, v in subject.dimension_dict.items()})
                        mdds = MemberDailyDimensionStatistics.sync_find_one(query)
                        if not mdds:
                            mdds = MemberDailyDimensionStatistics(
                                id=ObjectId(), daily_code=daily_code, member_cid=member.cid,
                                dimension=subject.dimension_dict)
                            insert_mdds_list.append(mdds)
                        if mdds:
                            mdds.province_code = member.province_code
                            mdds.city_code = complete_member_city_code(member.province_code, member.city_code)
                            mdds.district_code = member.district_code
                            mdds.gender = member.sex
                            mdds.age_group = member.age_group
                            mdds.education = member.education
                            mdds.category = member.category
                            mdds.subject_total_quantity += 1
                            if result.get('true_answer'):
                                mdds.subject_correct_quantity += 1
                            mdds.created_dt = history.created_dt
                            mdds.updated_dt = history.updated_dt
                            if mdds not in insert_mdds_list:
                                mdds.sync_save()
        if insert_mdds_list:
            MemberDailyDimensionStatistics.sync_insert_many(insert_mdds_list)

    except ValueError:
        trace_i = traceback.format_exc()
        result['msg'] = trace_i
        print(trace_i)


def _get_daily_code(dt: datetime.datetime = None):
    """
    获取对接标识
    :return:
    """
    if not dt:
        dt = datetime.datetime.now()
    return datetime2str(dt, date_format='%Y%m%d000000')


if __name__ == '__main__':
    t1 = datetime.datetime.now().replace(year=2019, month=5, day=5, hour=12, minute=0, second=0, microsecond=0)
    t2 = datetime.datetime.now().replace(year=2019, month=5, day=17, hour=12, minute=0, second=0, microsecond=0)
    history_list = MemberGameHistory.sync_find({'created_dt': {'$gte': t1, '$lte': t2}},
                                               read_preference=ReadPreference.PRIMARY).batch_size(128)
    for index, history in enumerate(history_list):
        start_dashboard_report_statistics_without_delay(history)
        print(index + 1, history.cid)
