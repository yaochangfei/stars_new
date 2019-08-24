"""
题库参数-科学素质题库参数雷达图
"""
import datetime
import traceback

import msgpack
from caches.redis_utils import RedisCache
from db import STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import SubjectDimension, MemberSubjectStatistics
from enums import KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from motorengine.stages.group_stage import GroupStage
from tasks import app
from tasks.instances.task_report_learning_member_quantity import early_warning
from tasks.instances.utils import early_warning_empty
from tasks.utils import save_cache_condition, get_yesterday

logger = log_utils.get_logging('task_report_subject_parameter_radar', 'task_report_subject_parameter_radar.log')


@app.task(bind=True, queue='subject_dimension_radar')
def start_statistics_subject_parameter_radar(self, cache_key, root_dimension_code, m_city_code_list, province_code_list,
                                             city_code_list, gender_list, age_group_list, education_list):
    """

    :param self:
    :param cache_key:
    :param root_dimension_code:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """
    logger.info('[START] SUBJECT_PARAMETER_RADAR(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_subject_parameter_radar', cache_key=cache_key,
                             root_dimension_code=root_dimension_code, m_city_code_list=m_city_code_list,
                             province_code_list=province_code_list, city_code_list=city_code_list,
                             gender_list=gender_list, age_group_list=age_group_list, education_list=education_list)
        do_statistics_subject_radar(cache_key=cache_key, root_dimension_code=root_dimension_code,
                                    m_city_code_list=m_city_code_list, province_code_list=province_code_list,
                                    city_code_list=city_code_list, gender_list=gender_list,
                                    age_group_list=age_group_list, education_list=education_list)
    except Exception:
        logger.warning(
            '[ERROR] SUBJECT_PARAMETER_RADAR(%s): cache_key=%s, locals=%s\n %s' % (
                self.request.id, cache_key, str(locals()), traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_subject_parameter_radar', cache_key, locals(), traceback.format_exc())
    logger.info('[ END ] SUBJECT_PARAMETER_RADAR(%s)' % self.request.id)


def do_statistics_subject_radar(cache_key, root_dimension_code, m_city_code_list,
                                province_code_list, city_code_list, gender_list, age_group_list,
                                education_list):
    """

    :param cache_key:
    :param root_dimension_code:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    data = []
    dimension = SubjectDimension.sync_find_one(dict(code=root_dimension_code, status=STATUS_SUBJECT_DIMENSION_ACTIVE))
    if not dimension:
        raise ValueError('can not find dimension by `root_dimension_code`(%s)' % root_dimension_code)

    stage_list = []
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    stage_list.append(MatchStage({'updated_dt': {'$lt': time_match}}))
    if m_city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': m_city_code_list}}))

    query_dict = {}
    if province_code_list:
        query_dict['province_code'] = {'$in': province_code_list}
    if city_code_list:
        query_dict['city_code'] = {'$in': city_code_list}
    if gender_list:
        query_dict['gender'] = {'$in': [int(s_gender) for s_gender in gender_list]}
    if age_group_list:
        query_dict['age_group'] = {'$in': [int(s_age_group) for s_age_group in age_group_list]}
    if education_list:
        query_dict['education'] = {'$in': [int(s_education) for s_education in education_list]}

    if query_dict:
        stage_list.append(MatchStage(query_dict))

    stage_list.append(GroupStage('dimension.%s' % dimension.cid, total={'$sum': '$total'},
                                 correct={'$sum': '$correct'}))
    stage_list.append(LookupStage(SubjectDimension, '_id', 'cid', 'dimension_list'))
    stat_result = MemberSubjectStatistics.sync_aggregate(stage_list)
    while True:
        try:
            mds = stat_result.next()
            if mds:
                code, title, ordered = '', '', 0
                if hasattr(mds, 'dimension_list') and mds.dimension_list:
                    dimension = mds.dimension_list[0]
                    if dimension:
                        code = dimension.code
                        title = dimension.title
                        ordered = dimension.ordered
                data.append(dict(
                    code=code,
                    title=title,
                    ordered=ordered,
                    correct=mds.correct,
                    total=mds.total
                ))
        except StopIteration:
            break
    if not data:
        early_warning_empty("start_statistics_subject_parameter_radar", cache_key, locals(), '获取维度正确率雷达图统计数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))
