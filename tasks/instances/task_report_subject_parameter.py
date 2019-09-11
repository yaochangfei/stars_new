"""
题库参数任务
"""
import traceback

import msgpack

from caches.redis_utils import RedisCache
from db.models import SubjectChoiceRules, MemberDailyStatistics
from enums import KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine.stages import MatchStage
from motorengine.stages.group_stage import GroupStage
from tasks import app
from tasks.instances.task_report_learning_member_quantity import early_warning
from tasks.instances.utils import early_warning_empty
from tasks.utils import save_cache_condition, get_yesterday

logger = log_utils.get_logging('task_report_learning_member_quantity')


@app.task(bind=True, queue='subject_quantity')
def start_statistics_subject_quantity(self, cache_key, m_province_code_list, m_city_code_list, s_province_code_list,
                                      s_city_code_list, s_gender_list, s_age_group_list, s_education_list):
    """

    :param self:
    :param cache_key:
    :param m_province_code_list:
    :param m_city_code_list:
    :param s_province_code_list:
    :param s_city_code_list:
    :param s_gender_list:
    :param s_age_group_list:
    :param s_education_list:
    :return:
    """
    logger.info('[START] MEMBER_QUANTITY_STATISTICS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_subject_quantity', cache_key=cache_key,
                             m_province_code_list=m_province_code_list, m_city_code_list=m_city_code_list,
                             s_province_code_list=s_province_code_list,
                             s_city_code_list=s_city_code_list, s_gender_list=s_gender_list,
                             s_age_group_list=s_age_group_list, s_education_list=s_education_list)
        do_statistics_subject_parameter(cache_key=cache_key,
                                        m_province_code_list=m_province_code_list, m_city_code_list=m_city_code_list,
                                        s_province_code_list=s_province_code_list,
                                        s_city_code_list=s_city_code_list, s_gender_list=s_gender_list,
                                        s_age_group_list=s_age_group_list, s_education_list=s_education_list)
    except Exception:
        logger.warning(
            '[ERROR] MEMBER_QUANTITY_STATISTICS(%s): params=%s\n %s' % (
                self.request.id, str(dict(cache_key=cache_key,
                                          m_province_code_list=m_province_code_list, m_city_code_list=m_city_code_list,
                                          s_province_code_list=s_province_code_list,
                                          s_city_code_list=s_city_code_list, s_gender_list=s_gender_list,
                                          s_age_group_list=s_age_group_list, s_education_list=s_education_list)),
                traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_subject_quantity',
                      cache_key, str(dict(cache_key=cache_key,
                                          m_province_code_list=m_province_code_list,
                                          m_city_code_list=m_city_code_list,
                                          s_province_code_list=s_province_code_list,
                                          s_city_code_list=s_city_code_list,
                                          s_gender_list=s_gender_list,
                                          s_age_group_list=s_age_group_list,
                                          s_education_list=s_education_list)),
                      traceback.format_exc())

    logger.info('[ END ] MEMBER_QUANTITY_STATISTICS(%s)' % self.request.id)


def do_statistics_subject_parameter(cache_key, m_province_code_list, m_city_code_list, s_province_code_list,
                                    s_city_code_list, s_gender_list, s_age_group_list, s_education_list):
    """

    :param cache_key:
    :param m_province_code_list:
    :param m_city_code_list:
    :param s_province_code_list:
    :param s_city_code_list:
    :param s_gender_list:
    :param s_age_group_list:
    :param s_education_list:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    data = {}
    max_q = None
    max_q_list = SubjectChoiceRules.sync_aggregate([GroupStage('max', max={'$max': '$quantity'})]).to_list(1)
    if max_q_list:
        max_q = max_q_list[0]
    if max_q and max_q.max > 0:
        stage_list = do_create_query(max_q.max + 1, m_province_code_list, m_city_code_list, s_province_code_list,
                                     s_city_code_list, s_gender_list, s_age_group_list, s_education_list)
        if stage_list:
            if stage_list:
                stat_result = None
                stat_result_list = MemberDailyStatistics.sync_aggregate(stage_list).to_list(1)
                if stat_result_list:
                    stat_result = stat_result_list[0]
                if stat_result:
                    for i in range(max_q.max + 1):
                        attr = str(i)
                        if hasattr(stat_result, attr):
                            data[attr] = getattr(stat_result, attr, 0)
    if not data:
        early_warning_empty("start_statistics_subject_quantity", cache_key,
                            str(dict(cache_key=cache_key,
                                     m_province_code_list=m_province_code_list,
                                     m_city_code_list=m_city_code_list,
                                     s_province_code_list=s_province_code_list,
                                     s_city_code_list=s_city_code_list,
                                     s_gender_list=s_gender_list,
                                     s_age_group_list=s_age_group_list,
                                     s_education_list=s_education_list)),
                            '学习趋势统计数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))


def do_create_query(max_q, m_province_code_list, m_city_code_list, s_province_code_list, s_city_code_list,
                    s_gender_list, s_age_group_list, s_education_list):
    """

    :param max_q:
    :param m_province_code_list:
    :param m_city_code_list:
    :param s_province_code_list:
    :param s_city_code_list:
    :param s_gender_list:
    :param s_age_group_list:
    :param s_education_list:
    :return:
    """
    if max_q is not None:
        stage_list = []
        match_dict = {}
        if m_province_code_list:
            match_dict['province_code'] = {'$in': m_province_code_list}
        if m_city_code_list:
            match_dict['city_code'] = {'$in': m_city_code_list}

        s_and_list = []
        #  取前一天凌晨12点之前的数据
        time_match = get_yesterday()
        s_and_list.append({'updated_dt': {'$lt': time_match}})
        if s_province_code_list:
            s_and_list.append({'province_code': {'$in': s_province_code_list}})
        if s_city_code_list:
            s_and_list.append({'city_code': {'$in': s_city_code_list}})
        if s_gender_list:
            s_and_list.append({'gender': {'$in': [int(s_gender) for s_gender in s_gender_list]}})
        if s_age_group_list:
            s_and_list.append({'age_group': {'$in': [int(s_age_group) for s_age_group in s_age_group_list]}})
        if s_education_list:
            s_and_list.append({'education': {'$in': [int(s_education) for s_education in s_education_list]}})

        if s_and_list:
            match_dict['$and'] = s_and_list
        if match_dict:
            stage_list.append(MatchStage(match_dict))

        group_dict = {}
        for i in range(max_q):
            group_dict[str(i)] = {
                '$sum': '$quantity_detail.%s' % i
            }
        if group_dict:
            stage_list.append(
                GroupStage(None, **group_dict)
            )
        return stage_list
    return None
