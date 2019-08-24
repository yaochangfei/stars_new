# !/usr/bin/python
# -*- coding:utf-8 -*-


import copy
import datetime
import time
import traceback

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db.models import MemberGameHistory, Member, DockingStatistics, Subject, MemberCheckPointHistory, SubjectDimension
from enums import KEY_PREFIX_TASK_DOCKING_STATISTICS, KEY_ALLOW_PROCESS_DOCKING_STATISTICS
from logger import log_utils
from tasks import app
from tasks.config import task_time_limit

logger = log_utils.get_logging('task_docking_statistics', 'task_docking_statistics.log')


async def start_docking_statistics(history_model, member: Member = None, docking_code=None):
    try:
        if not isinstance(history_model, (MemberGameHistory, MemberCheckPointHistory)):
            raise ValueError('"member_history" must be a instance of MemberGameHistory or MemberCheckPointHistory.')
        if member:
            if not isinstance(member, Member):
                raise ValueError('"member" must be a instance of member.')
        else:
            member = await Member.get_by_cid(history_model.member_cid)

        tag_key = '%s_%s%s' % (KEY_PREFIX_TASK_DOCKING_STATISTICS, member.cid, history_model.cid)
        tag = RedisCache.get(tag_key)
        if not tag:
            RedisCache.set(tag_key, 1, 2 * 24 * 60 * 60)
            # 创建对接数据记录
            docking_code = docking_code if docking_code else _get_docking_code()
            ds = await DockingStatistics.find_one(dict(docking_code=docking_code, member_cid=member.cid))
            if not ds:
                ds = DockingStatistics(docking_code=docking_code, member_cid=member.cid, member_code=member.code)
                await ds.save()
            if ds:
                # 添加任务
                return docking_statistics.delay(history_model, member, docking_code)
        else:
            logger.warning(
                'WARNING: Task repeat executed, history_cid=%s, member_code=%s ' % (history_model.cid, member.code))
    except Exception:
        logger.error(traceback.format_exc())
    return None


@app.task(bind=True)
def docking_statistics(self, history_model, member: Member, docking_code: str) -> dict:
    result = {'code': 0}
    if allowed_process():
        try:
            if self.request.id:
                stat_type = 'FIGHT'
                if isinstance(history_model, MemberCheckPointHistory):
                    stat_type = 'RACE'
                logger.info(
                    'START(%s): type=%s, history_cid=%s, member_code=%s' % (
                        self.request.id, stat_type, history_model.cid, member.code))

            ds = DockingStatistics.sync_find_one(dict(docking_code=docking_code, member_cid=member.cid))
            if ds:
                ds.member_code = member.code
                ds.province_code = member.province_code
                ds.city_code = member.city_code
                ds.sex = member.sex
                ds.age_group = member.age_group
                ds.education = member.education
                # 累计次数
                ds.total_times = ds.total_times + 1
                # 统计游戏题目数&正确数
                _, total_correct_quantity = _do_count_subject_quantity(ds, history_model)
                # 统计正确次数
                _do_count_correct_quantity(ds, total_correct_quantity)
                # 统计题目详情
                subject_list, subject_answer_dict = _do_count_subjects_detail(ds, history_model)
                # 统计维度详情
                _do_count_dimension_detail(ds, subject_list, subject_answer_dict)
                # 保存结果
                ds.updated_dt = datetime.datetime.now()
                ds.sync_save()

                result['code'] = 1
                result['msg'] = 'Succeed!'

            if self.request.id:
                logger.info('START(%s): result_code=%s' % (self.request.id, result.get('code')))
        except ValueError:
            logger.error(traceback.format_exc())
            result['msg'] = traceback.format_exc()
        finally:
            RedisCache.set(KEY_ALLOW_PROCESS_DOCKING_STATISTICS, 0)

    return result


def _do_count_subject_quantity(ds: DockingStatistics, history_model) -> (int, int):
    """
    统计题目总数及正确数
    :param history_model:
    :return:
    """
    if ds and history_model:
        total_quantity = 0
        total_correct_quantity = 0
        answer_list = history_model.result
        if answer_list:
            for answer in answer_list:
                if answer:
                    if answer.get('selected_option_cid'):
                        total_quantity += 1
                    if answer.get('true_answer'):
                        total_correct_quantity += 1
        # 记录结果
        ds.total_subject_quantity += total_quantity
        ds.total_subject_correct_quantity += total_correct_quantity

        return total_quantity, total_correct_quantity
    return 0, 0


def _do_count_correct_quantity(ds: DockingStatistics, total_correct_quantity=0):
    """
    统计答题正确次数
    :param ds: 统计数据Model
    :param total_correct_quantity: 正确总数量
    :return:
    """
    if ds.correct_quantity_detail is None:
        ds.correct_quantity_detail = {}
    if not ds.correct_quantity_detail.get(str(total_correct_quantity)):
        ds.correct_quantity_detail[str(total_correct_quantity)] = 0
    ds.correct_quantity_detail[str(total_correct_quantity)] += 1


def _do_count_subjects_detail(ds: DockingStatistics, history_model):
    """
    统计题目详情
    :param ds: 统计数据Model
    :param history_model: 会员游戏历史Model
    :return:
    """
    if ds and history_model:
        answer_list = history_model.result
        if answer_list:
            subject_cid_list, subject_answer_dict = [], {}
            for answer in answer_list:
                if answer and answer.get('selected_option_cid') and answer.get('subject_cid'):
                    subject_cid_list.append(answer.get('subject_cid'))
                    subject_answer_dict[answer.get('subject_cid')] = answer
            if subject_cid_list:
                subject_list = Subject.sync_find(dict(cid={'$in': subject_cid_list})).to_list(None)
                if subject_list:
                    for subject in subject_list:
                        answer = subject_answer_dict.get(subject.cid)
                        if answer:
                            if ds.subjects_detail is None:
                                ds.subjects_detail = {}
                            if ds.subjects_detail.get(subject.code) is None:
                                ds.subjects_detail[subject.code] = {}
                            if not ds.subjects_detail[subject.code].get('total'):
                                ds.subjects_detail[subject.code]['total'] = 0
                            if not ds.subjects_detail[subject.code].get('correct'):
                                ds.subjects_detail[subject.code]['correct'] = 0
                            ds.subjects_detail[subject.code]['total'] += 1
                            if answer.get('true_answer'):
                                ds.subjects_detail[subject.code]['correct'] += 1
                return subject_list, subject_answer_dict
    return [], {}


def _do_count_dimension_detail(ds: DockingStatistics, answered_subject_list, subject_answer_dict):
    """
    难度统计详情
    :param ds: 统计数据Model
    :param answered_subject_list: 回答的题目列表
    :param subject_answer_dict: 题目答案映射
    :return:
    """
    if ds and subject_answer_dict and answered_subject_list:
        if ds.dimension_detail is None:
            ds.dimension_detail = {}

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
                            pdd = get_dimension_info(p_dimension_cid, answered_correct)
                            if pdd:
                                p_code = pdd.get('code')
                                if p_code:
                                    if ds.dimension_detail.get(p_code) is None:
                                        ds.dimension_detail[p_code] = {}

                                    p_dimension_dict = ds.dimension_detail[p_code]
                                    c_dimension_cid = dimension_dict.get(p_dimension_cid)
                                    if c_dimension_cid:
                                        dd = get_dimension_info(c_dimension_cid, answered_correct)
                                        if dd:
                                            d_code = dd.get('code')
                                            if d_code:
                                                dd_dimension = p_dimension_dict.get(d_code)
                                                if dd_dimension is None:
                                                    dd_dimension = p_dimension_dict[d_code] = {}

                                                if p_dimension_dict.get('total') is None:
                                                    p_dimension_dict['total'] = 0
                                                p_dimension_dict['total'] += 1

                                                if dd_dimension.get('total') is None:
                                                    dd_dimension['total'] = 0
                                                dd_dimension['total'] += 1

                                                if dd.get('correct'):
                                                    if p_dimension_dict.get('correct') is None:
                                                        p_dimension_dict['correct'] = 0
                                                    p_dimension_dict['correct'] += 1
                                                    if dd_dimension.get('correct') is None:
                                                        dd_dimension['correct'] = 0
                                                    dd_dimension['correct'] += 1

                                            for o_cid in other_cid_list:
                                                o_pdd = get_dimension_info(o_cid, answered_correct)
                                                if o_pdd:
                                                    o_p_code = o_pdd.get('code')
                                                    if o_p_code:
                                                        o_pp_dimension = dd_dimension.get(o_p_code)
                                                        if o_pp_dimension is None:
                                                            o_pp_dimension = dd_dimension[o_p_code] = {}

                                                        o_dd_cid = dimension_dict.get(o_cid)
                                                        if o_dd_cid:
                                                            o_dd = get_dimension_info(o_dd_cid, answered_correct)
                                                            if o_dd:
                                                                o_dd_code = o_dd.get('code')
                                                                if o_dd_code:
                                                                    o_dd_dimension = o_pp_dimension.get(o_dd_code)
                                                                    if o_dd_dimension is None:
                                                                        o_dd_dimension = o_pp_dimension[o_dd_code] = {}
                                                                    if o_dd_dimension.get('total') is None:
                                                                        o_dd_dimension['total'] = 0
                                                                    o_dd_dimension['total'] += 1
                                                                    if o_pp_dimension.get('total') is None:
                                                                        o_pp_dimension['total'] = 0
                                                                    o_pp_dimension['total'] += 1

                                                                    if o_dd.get('correct'):
                                                                        if o_dd_dimension.get('correct') is None:
                                                                            o_dd_dimension['correct'] = 0
                                                                        o_dd_dimension['correct'] += 1
                                                                        if o_pp_dimension.get('correct') is None:
                                                                            o_pp_dimension['correct'] = 0
                                                                        o_pp_dimension['correct'] += 1


def get_dimension_info(dimension_cid, answered_correct=False):
    if dimension_cid:
        dimension = SubjectDimension.sync_get_by_cid(dimension_cid)
        if dimension:
            return {
                'cid': dimension.cid,
                'code': dimension.code,
                'title': dimension.title,
                'correct': 1 if answered_correct else 0
            }
    return None


def _get_docking_code(dt: datetime.datetime = None):
    """
    获取对接标识
    :return:
    """
    if not dt:
        dt = datetime.datetime.now()
    return datetime2str(dt, date_format='%Y%m%d000000')


def allowed_process():
    """
    是否允许开始处理数据
    :return:
    """
    while True:
        cache_value = RedisCache.get(KEY_ALLOW_PROCESS_DOCKING_STATISTICS)
        if cache_value in [None, '0', 0]:
            RedisCache.set(KEY_ALLOW_PROCESS_DOCKING_STATISTICS, 1, task_time_limit)
            return True
        else:
            time.sleep(0.2)
