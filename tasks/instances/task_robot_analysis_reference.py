# !/usr/bin/python
# -*- coding:utf-8 -*-

import time
import traceback

from bson import ObjectId

from caches.redis_utils import RedisCache
from db.models import MemberGameHistory, MemberCheckPointHistory, Member, FightRobotAnalysisReference, Subject, \
    SubjectOption
from enums import KEY_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from motorengine.stages.project_stage import ProjectStage
from tasks import app
from tasks.config import task_time_limit

logger = log_utils.get_logging(
    'task_robot_analysis_reference_statistics')


@app.task(bind=True, queue='robot_analysis_reference')
def task_robot_analysis_reference_statistics(self, history_model, member: Member = None):
    """
    机器人数据分析参照统计
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
                # 开始统计任务
                logger.info('START ROBOT_ANALYSIS_REFERENCE_STATISTICS(%s): history_cid=%s, member_cid=%s' % (
                    self.request.id if self.request.id else '-', history_model.cid, member.cid))

                do_robot_statistics(history_model, member)

                logger.info('START ROBOT_ANALYSIS_REFERENCE_STATISTICS(%s): history_cid=%s, member_cid=%s' % (
                    self.request.id if self.request.id else '-', history_model.cid, member.cid))

        except Exception:
            logger.error(traceback.format_exc())
        finally:
            RedisCache.delete(KEY_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE)
    return result


def do_robot_statistics(history_model, member):
    """
    统计数据
    :param history_model:
    :param member:
    :return:
    """
    if history_model and member:
        if history_model:
            answer_list: list = history_model.result
            if answer_list:
                for answer in answer_list:
                    if answer and answer.get('selected_option_cid'):
                        subject_cid = answer.get('subject_cid')
                        consume_time = answer.get('consume_time')
                        if subject_cid and consume_time:
                            true_answer = answer.get('true_answer')
                            analysis_reference = FightRobotAnalysisReference.sync_find_one(dict(
                                subject_cid=subject_cid,
                                gender=member.sex,
                                age_group=member.age_group,
                                education=member.education
                            ))
                            if not analysis_reference:
                                analysis_reference = FightRobotAnalysisReference(
                                    id=ObjectId(), subject_cid=subject_cid, gender=member.sex,
                                    age_group=member.age_group, education=member.education)
                            if true_answer:
                                # 计算正确平均耗时时间
                                avg_correct_seconds = analysis_reference.avg_correct_seconds
                                total_correct = analysis_reference.correct
                                avg_correct_seconds = (avg_correct_seconds / (
                                    total_correct if total_correct else 1) + consume_time) / (
                                                              (total_correct if total_correct else 0) + 1)
                                analysis_reference.avg_correct_seconds = \
                                    avg_correct_seconds if avg_correct_seconds > 1 else 1
                                # 保存正确数
                                analysis_reference.correct += 1
                            else:
                                # 计算错误平均耗时时间
                                avg_incorrect_seconds = analysis_reference.avg_incorrect_seconds
                                total_incorrect = analysis_reference.total - analysis_reference.correct
                                avg_incorrect_seconds = (avg_incorrect_seconds / (
                                    total_incorrect if total_incorrect > 0 else 1) + consume_time) / (
                                                                (total_incorrect if total_incorrect else 0) + 1)
                                analysis_reference.avg_incorrect_seconds = \
                                    avg_incorrect_seconds if avg_incorrect_seconds > 1 else 1
                            # 计算总数
                            analysis_reference.total += 1
                            if true_answer:
                                # 计算正确率
                                analysis_reference.accuracy = analysis_reference.correct / analysis_reference.total

                            if analysis_reference.words == 0:
                                analysis_reference.words = get_subject_words(subject_cid)
                            analysis_reference.sync_save()


def get_subject_words(subject_cid):
    if subject_cid:
        subject_list = Subject.sync_aggregate([
            MatchStage({'cid': subject_cid}),
            LookupStage(foreign=SubjectOption, local_field='cid', foreign_field='subject_cid',
                        as_list_name='option_list'),
            ProjectStage(**{'_id': False, 'title': '$title', 'o_title': '$option_list.title'})
        ]).to_list(1)
        if subject_list:
            subject = subject_list[0]
            title = subject.title
            o_title = ''.join(subject.o_title)
            return len(title + o_title)
    return 0


def allowed_process():
    """
    是否允许开始处理数据
    :return:
    """
    while True:
        cache_value = RedisCache.get(KEY_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE)
        if cache_value in [None, '0', 0]:
            RedisCache.set(KEY_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE, 1, task_time_limit)
            return True
        else:
            time.sleep(0.05)
