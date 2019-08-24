#! /usr/bin/python


import traceback

from bson import ObjectId
from db.models import Member, MemberGameHistory, Subject, MemberLearningDayDimensionStatistics
from pymongo import ReadPreference
from tasks.instances.task_report_dashboard_statistics import member_learning_day_dimension_statistics, \
    _sync_get_learning_code, complete_member_city_code


def start_dashboard_report_statistics_without_delay(history):
    try:
        member = Member.sync_get_by_cid(history.member_cid)
        if not member:
            print('--- no member cid, history_cid=%s' % history.cid)
            return

        # START 学习日会员维度统计
        member_learning_day_dimension_statistics(history, member)
        # END 学习日会员维度统计

    except Exception:
        print(traceback.format_exc())


def member_learning_day_dimension_statistics(history, member: Member):
    try:
        learning_code, result_list = _sync_get_learning_code(history), history.result if history.result else []
        insert_mldds_list = []
        for result in result_list:
            if result:
                subject_cid = result.get('subject_cid')
                if subject_cid:
                    subject = Subject.sync_get_by_cid(subject_cid)
                    if subject and subject.dimension_dict:
                        query = {'learning_code': learning_code, 'member_cid': member.cid}
                        query.update({'dimension.%s' % k: v for k, v in subject.dimension_dict.items()})
                        mldds = MemberLearningDayDimensionStatistics.sync_find_one(query, read_preference=ReadPreference.PRIMARY)
                        if not mldds:
                            mldds = MemberLearningDayDimensionStatistics(
                                id=ObjectId(), learning_code=learning_code, member_cid=member.cid,
                                dimension=subject.dimension_dict)
                            insert_mldds_list.append(mldds)
                        if mldds:
                            mldds.province_code = member.province_code
                            mldds.city_code = complete_member_city_code(member.province_code, member.city_code)
                            mldds.district_code = member.district_code
                            mldds.gender = member.sex
                            mldds.age_group = member.age_group
                            mldds.education = member.education
                            mldds.category = member.category
                            mldds.subject_total_quantity += 1
                            if result.get('true_answer'):
                                mldds.subject_correct_quantity += 1
                            mldds.created_dt = history.created_dt
                            mldds.updated_dt = history.updated_dt
                            if mldds not in insert_mldds_list:
                                mldds.sync_save()
        if insert_mldds_list:
            MemberLearningDayDimensionStatistics.sync_insert_many(insert_mldds_list)
    except ValueError:
        trace_i = traceback.format_exc()
        print(trace_i)


if __name__ == '__main__':
    history_list = MemberGameHistory.sync_find(read_preference=ReadPreference.PRIMARY).batch_size(128)
    for index, history in enumerate(history_list):
        start_dashboard_report_statistics_without_delay(history)
        print(index + 1, history.cid)
