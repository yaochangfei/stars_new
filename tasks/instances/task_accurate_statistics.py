# !/usr/bin/python
# -*- coding:utf-8 -*-


import time
import traceback

from pymongo import ReadPreference

from caches.redis_utils import RedisCache
from db import SEX_LIST, SEX_NONE, SEX_DICT, TYPE_AGE_GROUP_NONE, TYPE_AGE_GROUP_DICT, TYPE_EDUCATION_NONE, \
    STATUS_RESULT_GAME_PK_WIN, STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP, \
    STATUS_RESULT_GAME_PK_TIE_BREAK, TYPE_EDUCATION_DICT, TYPE_AGE_GROUP_LIST
from db.models import MemberGameHistory, Member, SubjectDimension, Subject, SubjectAccuracyStatistics, \
    MemberCheckPointHistory, MemberAccuracyStatistics
from enums import KEY_PREFIX_TASK_ACCURATE_STATISTICS, KEY_ALLOW_PROCESS_ACCURATE_STATISTICS
from logger import log_utils
from tasks import app
from tasks.config import task_time_limit

logger = log_utils.get_logging('task_accurate_statistics', 'task_accurate_statistics.log')


@app.task(bind=True, queue='accurate_statistics')
def start_accurate_statistics(self, history_model, member: Member = None):
    """
    会员游戏数据精确统计
    :param self: 任务对象
    :param history_model: 游戏历史
    :param member: 会员，默认为None
    :return:
    """
    result = {'code': 0}
    if allowed_process():
        try:
            if not isinstance(history_model, (MemberGameHistory, MemberCheckPointHistory)):
                raise ValueError('"history_model" must be a instance of MemberGameHistory or MemberCheckPointHistory.')
            if member:
                if not isinstance(member, Member):
                    raise ValueError('"member" must be a instance of member.')
            else:
                member = Member.sync_get_by_cid(history_model.member_cid)

            if member:
                stat_type = 'FIGHT'
                if isinstance(history_model, MemberCheckPointHistory):
                    stat_type = 'RACE'
                logger.info(
                    'START(%s): Accurate Statistics, type=%s, history_cid=%s, member_code=%s' % (
                        self.request.id, stat_type, history_model.cid, member.code))
                tag_key = '%s_%s%s' % (KEY_PREFIX_TASK_ACCURATE_STATISTICS, member.cid, history_model.cid)
                tag = RedisCache.get(tag_key)
                if not tag:
                    RedisCache.set(tag_key, 1, 2 * 24 * 60 * 60)
                    # 题目正确率
                    do_count_subject_accuracy(history_model, member)
                    # 会员正确率
                    do_count_member_accuracy(history_model, member)

                    result['code'] = 1
                    result['msg'] = 'Succeed!'
                else:
                    logger.warning(
                        'END(%s): [Accurate Statistics] repeat executed,  type=%s, history_cid=%s, member_code=%s ' % (
                            self.request.id, stat_type, history_model.cid, member.code))
        except Exception:
            logger.error(traceback.format_exc())
        finally:
            RedisCache.delete(KEY_ALLOW_PROCESS_ACCURATE_STATISTICS)

    return result


def do_count_subject_accuracy(history_model, member: Member):
    """
    计算维度正确率
    :param history_model: 游戏历史
    :param member: 会员
    :return:
    """
    try:
        if history_model and member:
            answer_results = history_model.result
            if answer_results:
                accuracy_stat = SubjectAccuracyStatistics.sync_find_one(
                    dict(record_flag=1), read_preference=ReadPreference.PRIMARY)
                if not accuracy_stat:
                    accuracy_stat = SubjectAccuracyStatistics()
                for answer in answer_results:
                    if answer:
                        # 会员属性
                        do_count_member_property_accuracy(answer, member, accuracy_stat)
                        # 维度信息
                        do_count_dimension_accuracy(answer, accuracy_stat)
                # 保存结果
                accuracy_stat.sync_save()
    except Exception:
        logger.error(traceback.format_exc())


def do_count_member_property_accuracy(answer: dict, member: Member, accuracy_stat: SubjectAccuracyStatistics):
    if answer and member:
        selected_option_cid = answer.get('selected_option_cid')
        if selected_option_cid:
            correct = answer.get('true_answer')
            # 性别
            gender = accuracy_stat.gender
            if gender is None:
                accuracy_stat.gender = {}
            if member.sex not in SEX_LIST:
                member.sex = SEX_NONE
            sex_str = str(member.sex)
            sex_stat = accuracy_stat.gender.get(sex_str)
            if not sex_stat:
                sex_stat = accuracy_stat.gender[sex_str] = {
                    'code': member.sex if member.sex else SEX_NONE,
                    'title': SEX_DICT.get(member.sex if member.sex else SEX_NONE, '未知')
                }

            if sex_stat.get('total') is None:
                sex_stat['total'] = 0
            sex_stat['total'] += 1
            if correct:
                if sex_stat.get('correct') is None:
                    sex_stat['correct'] = 0
                sex_stat['correct'] += 1

            # 年龄段
            age_group = accuracy_stat.age_group
            if age_group is None:
                accuracy_stat.age_group = {}
            if member.age_group not in TYPE_AGE_GROUP_LIST:
                member.age_group = TYPE_AGE_GROUP_NONE
            age_group_str = str(member.age_group)
            age_group_stat = accuracy_stat.age_group.get(age_group_str)
            if not age_group_stat:
                age_group_stat = accuracy_stat.age_group[age_group_str] = {
                    'code': member.age_group if member.age_group else TYPE_AGE_GROUP_NONE,
                    'title': TYPE_AGE_GROUP_DICT.get(member.age_group if member.age_group else TYPE_AGE_GROUP_NONE,
                                                     '未知')
                }
            if age_group_stat.get('total') is None:
                age_group_stat['total'] = 0
            age_group_stat['total'] += 1
            if correct:
                if age_group_stat.get('correct') is None:
                    age_group_stat['correct'] = 0
                age_group_stat['correct'] += 1

            # 受教育程度
            education = accuracy_stat.education
            if not education:
                accuracy_stat.education = {}
            education_str = str(member.education)
            education_stat = accuracy_stat.education.get(education_str)
            if education_stat is None:
                education_stat = accuracy_stat.education[education_str] = {
                    'code': member.education if member.education else TYPE_EDUCATION_NONE,
                    'title': TYPE_EDUCATION_DICT.get(member.education if member.education else TYPE_EDUCATION_NONE,
                                                     '未知')
                }

            if education_stat.get('total') is None:
                education_stat['total'] = 0
            education_stat['total'] += 1
            if correct:
                if education_stat.get('correct') is None:
                    education_stat['correct'] = 0
                education_stat['correct'] += 1


def do_count_dimension_accuracy(answer: dict, accuracy_stat: SubjectAccuracyStatistics):
    """
    计算维度正确率
    :param answer: 答案
    :param accuracy_stat: 统计Model
    :return:
    """
    if answer and accuracy_stat:
        selected_option_cid = answer.get('selected_option_cid')
        if selected_option_cid:
            correct = answer.get('true_answer')
            subject_cid = answer.get('subject_cid')
            # 统计维度
            if subject_cid:
                subject = Subject.sync_get_by_cid(subject_cid)
                if subject:
                    dimension_dict = subject.dimension_dict
                    if dimension_dict:
                        for p_dimension_cid, dimension_cid in dimension_dict.items():
                            dimension = accuracy_stat.dimension
                            if dimension is None:
                                accuracy_stat.dimension = {}
                            # 冗余根维度信息
                            if dimension.get(p_dimension_cid) is None:
                                dimension[p_dimension_cid] = {}
                                p_dimension: SubjectDimension = SubjectDimension.sync_get_by_cid(p_dimension_cid)
                                if p_dimension:
                                    if p_dimension.code:
                                        dimension[p_dimension_cid]['code'] = p_dimension.code
                                    if p_dimension.title:
                                        dimension[p_dimension_cid]['title'] = p_dimension.title
                                    if p_dimension.ordered:
                                        dimension[p_dimension_cid]['ordered'] = p_dimension.ordered
                                    dimension[p_dimension_cid]['children'] = {}
                            # 根维度统计
                            if dimension[p_dimension_cid].get('total') is None:
                                dimension[p_dimension_cid]['total'] = 0
                            if dimension[p_dimension_cid].get('correct') is None:
                                dimension[p_dimension_cid]['correct'] = 0
                            dimension[p_dimension_cid]['total'] += 1  # 总量
                            if correct:
                                dimension[p_dimension_cid]['correct'] += 1  # 正确量

                            children = dimension[p_dimension_cid]['children']
                            # 冗余子维度信息
                            if children.get(dimension_cid) is None:
                                children[dimension_cid] = {}
                                c_dimension: SubjectDimension = SubjectDimension.sync_get_by_cid(dimension_cid)
                                if c_dimension:
                                    if c_dimension.code:
                                        children[dimension_cid]['code'] = c_dimension.code
                                    if c_dimension.title:
                                        children[dimension_cid]['title'] = c_dimension.title
                                    if c_dimension.ordered:
                                        children[dimension_cid]['ordered'] = c_dimension.ordered
                            # 子维度统计
                            if children[dimension_cid].get('total') is None:
                                children[dimension_cid]['total'] = 0
                            if children[dimension_cid].get('correct') is None:
                                children[dimension_cid]['correct'] = 0
                            children[dimension_cid]['total'] += 1  # 总量
                            if correct:
                                children[dimension_cid]['correct'] += 1  # 正确量


def do_count_member_accuracy(history_model, member):
    if history_model and member:
        accuracy_stat = MemberAccuracyStatistics.sync_find_one(
            dict(member_cid=member.cid), read_preference=ReadPreference.PRIMARY)
        if not accuracy_stat:
            accuracy_stat = MemberAccuracyStatistics(member_cid=member.cid)

        do_count_member_fight_result(accuracy_stat, history_model, member)
        do_count_member_subject_accuracy(accuracy_stat, history_model, member)

        accuracy_stat.sync_save()


def do_count_member_fight_result(accuracy_stat: MemberAccuracyStatistics, history_model: MemberGameHistory,
                                 member: Member):
    """
    统计PK赛胜场结果
    :param accuracy_stat: 统计结果Model
    :param history_model: 游戏历史Model
    :param member: 会员Model
    :return:
    """
    if accuracy_stat and member and isinstance(history_model, MemberGameHistory):
        fight_status = history_model.status
        if fight_status == STATUS_RESULT_GAME_PK_WIN:
            accuracy_stat.win_times += 1
        elif fight_status == STATUS_RESULT_GAME_PK_FAILED:
            accuracy_stat.lose_times += 1
        elif fight_status == STATUS_RESULT_GAME_PK_GIVE_UP:
            accuracy_stat.escape_times += 1
        elif fight_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
            accuracy_stat.tie_times += 1


def do_count_member_subject_accuracy(accuracy_stat: MemberAccuracyStatistics, history_model, member: Member):
    """
    统计会员答题正确率
    :param accuracy_stat: 统计结果Model
    :param history_model: 游戏历史Model
    :param member: 会员Model
    :return:
    """
    if accuracy_stat and history_model and member:
        answer_results = history_model.result
        if answer_results:
            for answer in answer_results:
                if answer:
                    selected_option_cid = answer.get('selected_option_cid')
                    if selected_option_cid:
                        subject_cid = answer.get('subject_cid')
                        correct = answer.get('true_answer')
                        if subject_cid:
                            accuracy_stat.total_quantity += 1
                        if correct:
                            accuracy_stat.correct_quantity += 1
                        subject = Subject.sync_get_by_cid(subject_cid)
                        if subject:
                            dimension_dict = subject.dimension_dict
                            if dimension_dict:
                                for p_dimension_cid, dimension_cid in dimension_dict.items():
                                    dimension = accuracy_stat.dimension
                                    if dimension is None:
                                        accuracy_stat.dimension = {}
                                    # 冗余根维度信息
                                    if dimension.get(p_dimension_cid) is None:
                                        dimension[p_dimension_cid] = {}
                                        p_dimension: SubjectDimension = SubjectDimension.sync_get_by_cid(
                                            p_dimension_cid)
                                        if p_dimension:
                                            if p_dimension.code:
                                                dimension[p_dimension_cid]['code'] = p_dimension.code
                                            if p_dimension.title:
                                                dimension[p_dimension_cid]['title'] = p_dimension.title
                                            if p_dimension.ordered:
                                                dimension[p_dimension_cid]['ordered'] = p_dimension.ordered
                                            dimension[p_dimension_cid]['children'] = {}
                                    # 根维度统计
                                    if dimension[p_dimension_cid].get('total') is None:
                                        dimension[p_dimension_cid]['total'] = 0
                                    if dimension[p_dimension_cid].get('correct') is None:
                                        dimension[p_dimension_cid]['correct'] = 0
                                    dimension[p_dimension_cid]['total'] += 1  # 总量
                                    if correct:
                                        dimension[p_dimension_cid]['correct'] += 1  # 正确量

                                    children = dimension[p_dimension_cid]['children']
                                    # 冗余子维度信息
                                    if children.get(dimension_cid) is None:
                                        children[dimension_cid] = {}
                                        c_dimension: SubjectDimension = SubjectDimension.sync_get_by_cid(dimension_cid)
                                        if c_dimension:
                                            if c_dimension.code:
                                                children[dimension_cid]['code'] = c_dimension.code
                                            if c_dimension.title:
                                                children[dimension_cid]['title'] = c_dimension.title
                                            if c_dimension.ordered:
                                                children[dimension_cid]['ordered'] = c_dimension.ordered
                                    # 子维度统计
                                    if children[dimension_cid].get('total') is None:
                                        children[dimension_cid]['total'] = 0
                                    if children[dimension_cid].get('correct') is None:
                                        children[dimension_cid]['correct'] = 0
                                    children[dimension_cid]['total'] += 1  # 总量
                                    if correct:
                                        children[dimension_cid]['correct'] += 1  # 正确量


def allowed_process():
    """
    是否允许开始处理数据
    :return:
    """
    while True:
        cache_value = RedisCache.get(KEY_ALLOW_PROCESS_ACCURATE_STATISTICS)
        if cache_value in [None, '0', 0]:
            RedisCache.set(KEY_ALLOW_PROCESS_ACCURATE_STATISTICS, 1, task_time_limit)
            return True
        else:
            time.sleep(0.05)
