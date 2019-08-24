#! /usr/bin/python


import traceback

from db.models import MemberLearningDayStatistics, Member, MemberGameHistory
from pymongo import ReadPreference
from tasks.instances.task_report_dashboard_statistics import _sync_get_learning_code, \
    complete_member_city_code, _do_count_subject_correct_quantity, _do_count_correct_quantity, _do_get_subjects_detail, \
    _do_count_dimension_detail


def init_member_learning_day_statistics(history):
    """

    :param history:
    :return:
    """
    try:
        member = Member.sync_get_by_cid(history.member_cid)
        if not member:
            print('--- no member cid, history_cid=%s' % history.cid)
            return

            # START: 会员按学习日数据统计
        learning_code = _sync_get_learning_code(history)
        mls = MemberLearningDayStatistics.sync_find_one(dict(learning_code=learning_code, member_cid=member.cid),
                                                        read_preference=ReadPreference.PRIMARY)
        if not mls:
            # 创建会员学习日数据统计记录
            mls = MemberLearningDayStatistics(learning_code=learning_code, member_cid=member.cid)
            mls.sync_save()
        # 添加任务
        member_learning_day_statistics(history, member, learning_code)
        # END: 会员按学习日数据统计
    except Exception:
        print(traceback.format_exc())


def member_learning_day_statistics(history, member: Member, learning_code):
    try:
        mls = MemberLearningDayStatistics.sync_find_one(dict(learning_code=learning_code, member_cid=member.cid))
        if mls:
            mls.province_code = member.province_code
            city_code = complete_member_city_code(member.province_code, member.city_code)
            mls.city_code = city_code
            mls.district_code = member.district_code
            mls.gender = member.sex
            mls.age_group = member.age_group
            mls.education = member.education
            mls.category = member.category
            # 学习总次数
            mls.learn_times += 1
            # 答题正确数
            correct_quantity = _do_count_subject_correct_quantity(mls, history)
            # 统计答题正确数的次数
            _do_count_correct_quantity(mls, correct_quantity)
            # 获取题目详情
            subject_list, subject_answer_dict = _do_get_subjects_detail(history)
            # 统计维度详情
            _do_count_dimension_detail(mls, subject_list, subject_answer_dict)
            mls.created_dt = history.created_dt
            mls.updated_dt = history.updated_dt
            mls.sync_save()
    except ValueError:
        trace_i = traceback.format_exc()
        print(trace_i)


if __name__ == '__main__':
    history_list = MemberGameHistory.sync_find(read_preference=ReadPreference.PRIMARY).batch_size(128)
    for index, history in enumerate(history_list):
        init_member_learning_day_statistics(history)
        print(index + 1, history.cid)
