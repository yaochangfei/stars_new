#! /usr/bin/python


import datetime
import traceback

from commons.common_utils import datetime2str
from db.models import Member, MemberDailyStatistics, MemberGameHistory
from pymongo import ReadPreference
from tasks.instances.task_report_dashboard_statistics import _do_count_subject_correct_quantity, \
    _do_count_correct_quantity, _do_get_subjects_detail, _do_count_dimension_detail, complete_member_city_code


def start_dashboard_report_statistics_without_delay(history):
    """

    :param history:
    :return:
    """
    try:
        daily_code = _get_daily_code(history.fight_datetime)
        member = Member.sync_get_by_cid(history.member_cid)
        if not member:
            print('--- no member cid, history_cid=%s' % history.cid)

        mds = MemberDailyStatistics.sync_find_one(
            dict(daily_code=daily_code, member_cid=member.cid))

        if not mds:
            mds = MemberDailyStatistics(daily_code=daily_code, member_cid=member.cid)
            mds.sync_save()
        if mds:
            member_daily_statistics(history, member, daily_code)

    except Exception:
        print(traceback.format_exc())


def _get_daily_code(dt: datetime.datetime = None):
    """
    获取对接标识
    :return:
    """
    if not dt:
        dt = datetime.datetime.now()
    return datetime2str(dt, date_format='%Y%m%d000000')


def member_daily_statistics(history, member: Member, daily_code):
    mds = MemberDailyStatistics.sync_find_one(
        dict(daily_code=daily_code, member_cid=member.cid), read_preference=ReadPreference.PRIMARY)
    if mds:
        mds.province_code = member.province_code
        mds.city_code = complete_member_city_code(member.province_code, member.city_code)
        mds.district_code = member.district_code
        mds.gender = member.sex
        mds.age_group = member.age_group
        mds.education = member.education
        mds.category = member.category
        # 学习总次数
        mds.learn_times += 1
        # 答题正确数
        correct_quantity = _do_count_subject_correct_quantity(mds, history)
        # 统计答题正确数的次数
        _do_count_correct_quantity(mds, correct_quantity)
        # 获取题目详情
        subject_list, subject_answer_dict = _do_get_subjects_detail(history)
        # 统计维度详情
        _do_count_dimension_detail(mds, subject_list, subject_answer_dict)
        mds.created_dt = history.created_dt
        mds.updated_dt = history.updated_dt
        mds.sync_save()


if __name__ == '__main__':
    history_list = MemberGameHistory.sync_find(read_preference=ReadPreference.PRIMARY).batch_size(128)
    for index, history in enumerate(history_list):
        start_dashboard_report_statistics_without_delay(history)
        print(index + 1, history.cid)
