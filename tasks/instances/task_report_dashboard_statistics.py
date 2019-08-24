# !/usr/bin/python
# -*- coding:utf-8 -*-


import copy
import datetime
import time
import traceback

from bson import ObjectId
from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db.models import Member, MemberGameHistory, MemberCheckPointHistory, MemberDailyStatistics, Subject, \
    MemberSubjectStatistics, MemberDimensionStatistics, MemberLearningDayStatistics, MemberDailyDimensionStatistics, \
    MemberLearningDayDimensionStatistics
from enums import KEY_PREFIX_TASK_REPORT_DATA_STATISTICS, KEY_ALLOW_TASK_MEMBER_DAILY_STATISTICS, \
    KEY_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS, KEY_ALLOW_TASK_MEMBER_DIMENSION_STATISTICS, \
    KEY_ALLOW_TASK_MEMBER_LEARNING_DAYS_STATISTICS, KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS, \
    KEY_ALLOW_TASK_MEMBER_LEARNING_DAY_DIMENSION_STATISTICS
from logger import log_utils
from motorengine.stages import MatchStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from pymongo import ReadPreference
from tasks import app
from tasks.config import task_time_limit

logger = log_utils.get_logging('task_dashboard_report_statistics', 'task_dashboard_report_statistics.log')


async def start_dashboard_report_statistics(
        history, member: Member = None, daily_code: str = None, learning_code: str = None):
    try:
        if not isinstance(history, MemberGameHistory):
            raise ValueError('"member_history" must be a instance of MemberGameHistory or MemberCheckPointHistory.')
        if member:
            if not isinstance(member, Member):
                raise ValueError('"member" must be a instance of member.')
        else:
            member = await Member.get_by_cid(history.member_cid)

        tag_key = '%s_%s%s' % (KEY_PREFIX_TASK_REPORT_DATA_STATISTICS, member.cid, history.cid)
        tag = RedisCache.get(tag_key)
        if not tag:
            RedisCache.set(tag_key, 1, 2 * 24 * 60 * 60)

            # START: 会员每日数据统计
            daily_code = daily_code if daily_code else _get_daily_code(history.fight_datetime)
            # mds = await MemberDailyStatistics.find_one(dict(daily_code=daily_code, member_cid=member.cid))
            # if not mds:
            #     # 创建会员每日数据统计记录
            #     mds = MemberDailyStatistics(daily_code=daily_code, member_cid=member.cid)
            #     await mds.save()
            # if mds:
            #     # 添加任务
            member_daily_statistics.delay(history, member, daily_code)
            # END: 会员每日数据统计

            # START: 会员按学习日数据统计
            learning_code = learning_code if learning_code else await _get_learning_code(history)
            # mls = await MemberLearningDayStatistics.find_one(dict(learning_code=learning_code, member_cid=member.cid))
            # if not mls:
            #     # 创建会员学习日数据统计记录
            #     mls = MemberLearningDayStatistics(learning_code=learning_code, member_cid=member.cid)
            #     await mls.save()
            # if mds:
            # 添加任务
            member_learning_day_statistics.delay(history, member, learning_code)
            # END: 会员按学习日数据统计

            # START 自然日会员维度统计
            member_daily_dimension_statistics.delay(history, member)
            # END 自然日会员维度统计

            # START 学习日会员维度统计
            member_learning_day_dimension_statistics.delay(history, member)
            # END 学习日会员维度统计

            # START: 会员题目数据统计
            answer_list = history.result
            if answer_list:
                for answer in answer_list:
                    if answer.get('subject_cid') and answer.get('selected_option_cid'):
                        # 添加任务
                        member_subject_statistics.delay(history, answer, member)
            # END: 会员题目数据统计
        else:
            logger.warning(
                'WARNING: Task repeat executed, history_cid=%s, member_code=%s ' % (history.cid, member.code))
    except Exception:
        logger.error(traceback.format_exc())
    return None


async def start_dashboard_report_statistics_without_delay(
        history, member: Member = None, daily_code: str = None, learning_code: str = None):
    try:
        if not isinstance(history, MemberGameHistory):
            raise ValueError('"member_history" must be a instance of MemberGameHistory or MemberCheckPointHistory.')
        if member:
            if not isinstance(member, Member):
                raise ValueError('"member" must be a instance of member.')
        else:
            member = await Member.get_by_cid(history.member_cid)

        tag_key = '%s_%s%s' % (KEY_PREFIX_TASK_REPORT_DATA_STATISTICS, member.cid, history.cid)
        tag = RedisCache.get(tag_key)
        if not tag:
            RedisCache.set(tag_key, 1, 2 * 24 * 60 * 60)

            # START: 会员每日数据统计
            daily_code = daily_code if daily_code else _get_daily_code(history.fight_datetime)
            member_daily_statistics(history, member, daily_code)
            # END: 会员每日数据统计

            # START: 会员按学习日数据统计
            learning_code = learning_code if learning_code else await _get_learning_code(history)
            # 添加任务
            member_learning_day_statistics(history, member, learning_code)
            # END: 会员按学习日数据统计

            # START 自然日会员维度统计
            member_daily_dimension_statistics(history, member)
            # END 自然日会员维度统计

            # START 学习日会员维度统计
            member_learning_day_dimension_statistics(history, member)
            # END 学习日会员维度统计

            # START: 会员题目数据统计
            answer_list = history.result
            if answer_list:
                for answer in answer_list:
                    if answer.get('subject_cid') and answer.get('selected_option_cid'):
                        # 添加任务
                        member_subject_statistics(history, answer, member)
            # END: 会员题目数据统计
        else:
            logger.warning(
                'WARNING: Task repeat executed, history_cid=%s, member_code=%s ' % (history.cid, member.code))
    except Exception:
        logger.error(traceback.format_exc())
    return None


@app.task(bind=True, queue='report_dashboard_statistics')
def member_learning_day_statistics(self, history, member: Member, learning_code):
    result = {'code': 0}
    if history and member:
        try:
            logger.info('START MEMBER_LEARNING_DAY_STATISTICS(%s): history_cid=%s' % (
                self.request.id if self.request.id else '-', history.cid))
            mls = MemberLearningDayStatistics.sync_find_one(dict(learning_code=learning_code, member_cid=member.cid))
            if not mls:
                mls = MemberLearningDayStatistics(learning_code=learning_code, member_cid=member.cid)

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
            mls.created_dt = history.fight_datetime
            mls.updated_dt = history.fight_datetime
            mls.sync_save()
            logger.info('END MEMBER_LEARNING_DAY_STATISTICS(%s): result_code=%s' % (
                self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)

    return result


@app.task(bind=True, queue='report_dashboard_statistics')
def member_daily_statistics(self, history, member: Member, daily_code):
    result = {'code': 0}
    if history and member and daily_code:
        try:
            logger.info('START MEMBER_DAILY_STATISTICS(%s): history_cid=%s' % (
                self.request.id if self.request.id else '-', history.cid))
            mds = MemberDailyStatistics.sync_find_one(
                dict(daily_code=daily_code, member_cid=member.cid), read_preference=ReadPreference.PRIMARY)
            if not mds:
                mds = MemberDailyStatistics(daily_code=daily_code, member_cid=member.cid)

            mds.province_code = member.province_code
            city_code = complete_member_city_code(member.province_code, member.city_code)
            mds.city_code = city_code
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
            mds.created_dt = history.fight_datetime
            mds.updated_dt = history.fight_datetime
            mds.sync_save()
            logger.info('END MEMBER_DAILY_STATISTICS(%s): result_code=%s' % (
                self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)

    return result


@app.task(bind=True, queue='report_dashboard_statistics')
def member_subject_statistics(self, history, answer: dict, member: Member):
    """
    会员题目统计分析
    :param self: 任务对象
    :param history: 历史
    :param answer: 答案
    :param member: 会员
    :return:
    """
    result = {'code': 0}
    if history and answer and member and allowed_process(KEY_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS):
        try:
            logger.info('START MEMBER_SUBJECT_STATISTICS(%s): history_cid=%s' % (
                self.request.id if self.request.id else '-', history.cid))

            mds = MemberSubjectStatistics.sync_find_one(
                dict(province_code=member.province_code, city_code=member.city_code,
                     district_code=member.district_code, gender=member.sex, age_group=member.age_group,
                     education=member.education, category=member.category,
                     subject_cid=answer.get('subject_cid')))
            if not mds:
                mds = MemberSubjectStatistics(province_code=member.province_code,
                                              city_code=member.city_code,
                                              district_code=member.district_code, gender=member.sex,
                                              age_group=member.age_group,
                                              education=member.education, category=member.category,
                                              subject_cid=answer.get('subject_cid'))

            subject = Subject.sync_get_by_cid(mds.subject_cid)
            mds.dimension = subject.dimension_dict
            mds.province_code = member.province_code
            mds.city_code = member.city_code
            mds.district_code = member.district_code
            mds.gender = member.sex
            mds.age_group = member.age_group
            mds.education = member.education
            mds.category = member.category
            # 统计题目正确率
            _do_member_subject_accuracy(answer, mds)
            # 保存结果
            mds.created_dt = history.fight_datetime
            mds.updated_dt = history.fight_datetime
            mds.sync_save()

            logger.info('END MEMBER_SUBJECT_STATISTICS(%s): result_code=%s' % (
                self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)
        finally:
            release_process(KEY_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS)

    return result


@app.task(bind=True, queue='report_dashboard_statistics')
def member_dimension_statistics(self, history, dimension_dict: dict, answer: dict, other_cid_list: list, member: Member,
                                mds_cid: str):
    """
    维度统计
    :param self: 任务对象
    :param history: 答题历史
    :param dimension_dict: 题目维度
    :param answer: 题目对应的答案
    :param other_cid_list: 需要交叉的维度
    :param member: 会员
    :param mds_cid: 维度统计表CID
    :return:
    """
    result = {'code': 0}
    if history and dimension_dict and answer and other_cid_list and member and allowed_process(
            KEY_ALLOW_TASK_MEMBER_DIMENSION_STATISTICS):
        try:
            if self.request.id:
                logger.info('START MEMBER_DIMENSION_STATISTICS(%s): history_cid=%s' % (self.request.id, history.cid))
            mds: MemberDimensionStatistics = MemberDimensionStatistics.sync_get_by_cid(
                mds_cid, read_preference=ReadPreference.PRIMARY)
            if mds:
                mds.province_code = member.province_code
                city_code = complete_member_city_code(member.province_code, member.city_code)
                mds.city_code = city_code
                mds.district_code = member.district_code
                mds.gender = member.sex
                mds.age_group = member.age_group
                mds.education = member.education
                mds.category = member.category
                # 统计维度详情
                _do_member_dimension_detail(other_cid_list, dimension_dict, answer, mds)
                mds.created_dt = history.fight_datetime
                mds.updated_dt = history.fight_datetime
                # 保存结果
                mds.sync_save()

            if self.request.id:
                logger.info(
                    'END MEMBER_DIMENSION_STATISTICS(%s): result_code=%s' % (self.request.id, result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)
        finally:
            release_process(KEY_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS)

    return result


@app.task(bind=True, queue='report_dashboard_statistics')
def member_daily_dimension_statistics(self, history, member: Member):
    result = {'code': 0}
    if history and member and allowed_process(KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS):
        try:
            logger.info('START MEMBER_DAILY_DIMENSION_STATISTICS(%s): history_cid=%s' % (
                self.request.id if self.request.id else '-', history.cid))
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
                            mdds = MemberDailyDimensionStatistics.sync_find_one(
                                query, read_preference=ReadPreference.PRIMARY)
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
                                mdds.created_dt = history.fight_datetime
                                mdds.updated_dt = history.fight_datetime
                                if mdds not in insert_mdds_list:
                                    mdds.sync_save()
            if insert_mdds_list:
                MemberDailyDimensionStatistics.sync_insert_many(insert_mdds_list)

            logger.info('END MEMBER_DAILY_DIMENSION_STATISTICS(%s): result_code=%s' % (
                self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)
        finally:
            release_process(KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS)

    return result


@app.task(bind=True, queue='report_dashboard_statistics')
def member_learning_day_dimension_statistics(self, history, member: Member):
    result = {'code': 0}
    if history and member and allowed_process(KEY_ALLOW_TASK_MEMBER_LEARNING_DAY_DIMENSION_STATISTICS):
        try:
            logger.info('START MEMBER_LEARNING_DAY_DIMENSION_STATISTICS(%s): history_cid=%s' % (
                self.request.id if self.request.id else '-', history.cid))
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
                            mldds = MemberLearningDayDimensionStatistics.sync_find_one(
                                query, read_preference=ReadPreference.PRIMARY)
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
                                mldds.created_dt = history.fight_datetime
                                mldds.updated_dt = history.fight_datetime
                                if mldds not in insert_mldds_list:
                                    mldds.sync_save()
            if insert_mldds_list:
                MemberLearningDayDimensionStatistics.sync_insert_many(insert_mldds_list)
            logger.info('END MEMBER_LEARNING_DAY_DIMENSION_STATISTICS(%s): result_code=%s' % (
                self.request.id if self.request.id else '-', result.get('code')))
        except ValueError:
            trace_i = traceback.format_exc()
            result['msg'] = trace_i
            logger.error(trace_i)
        finally:
            release_process(KEY_ALLOW_TASK_MEMBER_LEARNING_DAY_DIMENSION_STATISTICS)

    return result


def _do_count_subject_correct_quantity(mds, history):
    """
    题目正确数
    :param history:
    :return:
    """
    if history:
        total_quantity, correct_quantity = 0, 0
        answer_list = history.result
        if answer_list:
            for answer in answer_list:
                if answer:
                    if answer.get('selected_option_cid'):
                        total_quantity += 1
                        if answer.get('true_answer'):
                            correct_quantity += 1

        mds.subject_total_quantity += total_quantity
        mds.subject_correct_quantity += correct_quantity

        return correct_quantity
    return 0


def _do_count_correct_quantity(mds, total_correct_quantity=0):
    """
    统计答题正确次数
    :param mds: 统计数据Model
    :param total_correct_quantity: 正确总数量
    :return:
    """
    if mds.quantity_detail is None:
        mds.quantity_detail = {}
    if not mds.quantity_detail.get(str(total_correct_quantity)):
        mds.quantity_detail[str(total_correct_quantity)] = 0
    mds.quantity_detail[str(total_correct_quantity)] += 1


def _do_get_subjects_detail(history):
    """
    题目详情
    :param history: 会员游戏历史Model
    :return:
    """
    if history:
        answer_list = history.result
        if answer_list:
            subject_cid_list, subject_answer_dict = [], {}
            for answer in answer_list:
                if answer and answer.get('selected_option_cid') and answer.get('subject_cid'):
                    subject_cid_list.append(answer.get('subject_cid'))
                    subject_answer_dict[answer.get('subject_cid')] = answer
            if subject_cid_list:
                subject_list = Subject.sync_find(dict(cid={'$in': subject_cid_list})).to_list(None)
                return subject_list, subject_answer_dict
    return [], {}


def _do_member_subject_accuracy(answer: dict, mds):
    """
    统计题目正确率
    :param answer:
    :param mds:
    :return:
    """
    if answer and mds:
        if answer.get('selected_option_cid'):
            mds.total += 1
            if answer.get('true_answer'):
                mds.correct += 1
            mds.accuracy = mds.correct / mds.total


def _do_count_dimension_detail(mds, answered_subject_list, subject_answer_dict):
    """
    会员日常统计详情
    :param mds: 统计数据Model
    :param answered_subject_list: 回答的题目列表
    :param subject_answer_dict: 题目答案映射
    :return:
    """
    if mds and subject_answer_dict and answered_subject_list:
        if mds.dimension_detail is None:
            mds.dimension_detail = {}

        for subject in answered_subject_list:
            if subject:
                dimension_dict: dict = subject.dimension_dict
                if dimension_dict:
                    for p_dimension_cid in dimension_dict.keys():
                        other_cid_list: list = copy.deepcopy(list(dimension_dict.keys()))
                        p_dimension_cid = other_cid_list.pop(other_cid_list.index(p_dimension_cid))

                        answer = subject_answer_dict.get(subject.cid)
                        if answer:
                            # 是否回答正确
                            answered_correct = False
                            if answer.get('selected_option_cid') and answer.get('true_answer'):
                                answered_correct = True
                            # 统计每个维度
                            if p_dimension_cid:
                                if mds.dimension_detail.get(p_dimension_cid) is None:
                                    mds.dimension_detail[p_dimension_cid] = {}

                                p_dimension_dict = mds.dimension_detail[p_dimension_cid]
                                c_dimension_cid = dimension_dict.get(p_dimension_cid)
                                if c_dimension_cid:
                                    dd_dimension = p_dimension_dict.get(c_dimension_cid)
                                    if dd_dimension is None:
                                        dd_dimension = p_dimension_dict[c_dimension_cid] = {}

                                    if p_dimension_dict.get('total') is None:
                                        p_dimension_dict['total'] = 0
                                    p_dimension_dict['total'] += 1

                                    if dd_dimension.get('total') is None:
                                        dd_dimension['total'] = 0
                                    dd_dimension['total'] += 1

                                    if answered_correct:
                                        if p_dimension_dict.get('correct') is None:
                                            p_dimension_dict['correct'] = 0
                                        p_dimension_dict['correct'] += 1
                                        if dd_dimension.get('correct') is None:
                                            dd_dimension['correct'] = 0
                                        dd_dimension['correct'] += 1


def _do_member_dimension_detail(other_cid_list, dimension_dict, answer, mds):
    """
    维度统计详情
    :param other_cid_list: 其他维度
    :param dimension_dict: 题目维度详情
    :param answer: 本题答案
    :param mds: 维度统计
    :return:
    """
    if other_cid_list and dimension_dict and answer and mds:
        if mds.cross_dimension is None:
            mds.cross_dimension = {}
        if mds.total is None:
            mds.total = 0
        mds.total += 1
        if mds.correct is None:
            mds.correct = 0
        if answer.get('selected_option_cid') and answer.get('true_answer'):
            mds.correct += 1
        for p_dimension_cid in other_cid_list:
            if p_dimension_cid:
                if mds.cross_dimension.get(p_dimension_cid) is None:
                    mds.cross_dimension[p_dimension_cid] = {}
                c_dimension_cid = dimension_dict.get(p_dimension_cid)
                p_dimension_dict = mds.cross_dimension[p_dimension_cid]
                if c_dimension_cid:
                    c_dimension_dict = p_dimension_dict.get(c_dimension_cid)
                    if c_dimension_dict is None:
                        c_dimension_dict = p_dimension_dict[c_dimension_cid] = {}
                    if p_dimension_dict.get('total') is None:
                        p_dimension_dict['total'] = 0
                    p_dimension_dict['total'] += 1
                    if c_dimension_dict.get('total') is None:
                        c_dimension_dict['total'] = 0
                    c_dimension_dict['total'] += 1
                    if answer.get('selected_option_cid') and answer.get('true_answer'):
                        if p_dimension_dict.get('correct') is None:
                            p_dimension_dict['correct'] = 0
                        p_dimension_dict['correct'] += 1
                        if c_dimension_dict.get('correct') is None:
                            c_dimension_dict['correct'] = 0
                        c_dimension_dict['correct'] += 1


def _get_daily_code(dt: datetime.datetime = None):
    """
    获取对接标识
    :return:
    """
    if not dt:
        dt = datetime.datetime.now()
    return datetime2str(dt, date_format='%Y%m%d000000')


def _sync_get_learning_code(history):
    """
    获取学习日编码
    :param member_cid: 会员CID
    :return:
    """
    if history:
        l_code = RedisCache.get('LEARNING_STATISTICS_CODE_%s' % history.cid)
        if not l_code:
            prev_datetime = copy.deepcopy(history.fight_datetime).replace(
                hour=23, minute=59, second=59, microsecond=999999) - datetime.timedelta(days=1)
            match_stage = MatchStage({
                'member_cid': history.member_cid,
                'fight_datetime': {'$lte': prev_datetime}
            })
            project_stage = ProjectStage(date={'$dateToString': {'format': '%Y%m%d', 'date': '$fight_datetime'}})
            group_stage = GroupStage('date')

            mgh_cursor = MemberGameHistory.sync_aggregate(
                [match_stage, project_stage, group_stage], read_preference=ReadPreference.PRIMARY)
            mch_cursor = MemberCheckPointHistory.sync_aggregate(
                [match_stage, project_stage, group_stage], read_preference=ReadPreference.PRIMARY)
            tmp_dict = {}
            for mgh in mgh_cursor:
                if mgh:
                    tmp_dict[mgh.id] = int(mgh.id)
            for mch in mch_cursor:
                if mch:
                    tmp_dict[mch.id] = int(mch.id)
            l_code = 1
            if tmp_dict:
                l_code = len(tmp_dict.keys()) + 1
            remain_seconds = get_day_remain_seconds()
            if remain_seconds:
                RedisCache.set('LEARNING_STATISTICS_CODE_%s' % history.member_cid, l_code, remain_seconds)
        else:
            l_code = int(l_code)
        return l_code
    return None


async def _get_learning_code(history):
    """
    获取学习日编码
    :param member_cid: 会员CID
    :return:
    """
    if history:
        l_code = RedisCache.get('LEARNING_STATISTICS_CODE_%s' % history.cid)
        if not l_code:
            prev_datetime = copy.deepcopy(history.fight_datetime).replace(hour=23, minute=59, second=59,
                                                                          microsecond=999999) - datetime.timedelta(
                days=1)
            match_stage = MatchStage({
                'member_cid': history.member_cid,
                'fight_datetime': {'$lte': prev_datetime}
            })
            project_stage = ProjectStage(date={'$dateToString': {'format': '%Y%m%d', 'date': '$fight_datetime'}})
            group_stage = GroupStage('date')

            mgh_cursor = MemberGameHistory.aggregate([match_stage, project_stage, group_stage])
            # mch_cursor = MemberCheckPointHistory.aggregate([match_stage, project_stage, group_stage])

            tmp_dict = {}
            while await mgh_cursor.fetch_next:
                mgh = mgh_cursor.next_object()
                if mgh:
                    tmp_dict[mgh.id] = int(mgh.id)
            # while await mch_cursor.fetch_next:
            #     mch = mch_cursor.next_object()
            #     if mch:
            #         tmp_dict[mch.id] = int(mch.id)
            l_code = 1
            if tmp_dict:
                l_code = len(tmp_dict.keys()) + 1
            remain_seconds = get_day_remain_seconds()
            if remain_seconds:
                RedisCache.set('LEARNING_STATISTICS_CODE_%s' % history.member_cid, l_code, remain_seconds)
        else:
            l_code = int(l_code)
        return l_code
    return None


def get_day_remain_seconds():
    try:
        end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        return (end_datetime - datetime.datetime.now()).seconds
    except Exception:
        pass
    return None


def allowed_process(key: str):
    """
    是否允许开始处理数据
    :return:
    """
    if key:
        while True:
            cache_value = RedisCache.get(key)
            if cache_value in [None, '0', 0]:
                RedisCache.set(key, 1, task_time_limit)
                return True
            else:
                time.sleep(0.01)
    return False


def release_process(key: str):
    """
    释放任务锁
    :param key:
    :return:
    """
    if key:
        RedisCache.delete(key)
        return True
    return False


def complete_member_city_code(province_code, city_code):
    """
    直辖市city_code变更
    :param province_code:
    :param city_code:
    :return:
    """
    match_code_list = ['110000', '120000', '310000', '500000']
    match_code_dict = {'110000': '110100', '120000': '120100', '310000': '310100', '500000': '500100'}
    if province_code and province_code in match_code_list:
        city_code = match_code_dict.get(province_code)
    return city_code
