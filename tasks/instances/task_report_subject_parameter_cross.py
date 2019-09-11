"""
题库参数-科学素质题库参数比较分析
"""
import datetime
import traceback

import msgpack
from caches.redis_utils import RedisCache
from db import STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import SubjectDimension, MemberSubjectStatistics
from enums import KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage
from motorengine.stages.group_stage import GroupStage
from tasks import app
from tasks.instances.task_report_learning_member_quantity import early_warning
from tasks.instances.utils import early_warning_empty
from tasks.utils import save_cache_condition, get_yesterday

logger = log_utils.get_logging('task_report_subject_parameter_cross')


@app.task(bind=True, queue='subject_dimension_cross')
def start_statistics_subject_parameter_cross(self, cache_key, main_dimension_code, second_dimension_code,
                                             m_city_code_list, province_code_list, city_code_list, gender_list,
                                             age_group_list, education_list):
    """

    :param self:
    :param cache_key:
    :param main_dimension_code:
    :param second_dimension_code:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """
    logger.info('[START] SUBJECT_PARAMETER_CROSS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_subject_parameter_cross', cache_key=cache_key,
                             main_dimension_code=main_dimension_code, second_dimension_code=second_dimension_code,
                             m_city_code_list=m_city_code_list, province_code_list=province_code_list,
                             city_code_list=city_code_list, gender_list=gender_list,
                             age_group_list=age_group_list, education_list=education_list)
        do_statistics_subject_cross(cache_key=cache_key, main_dimension_code=main_dimension_code,
                                    second_dimension_code=second_dimension_code, m_city_code_list=m_city_code_list,
                                    province_code_list=province_code_list, city_code_list=city_code_list,
                                    gender_list=gender_list, age_group_list=age_group_list,
                                    education_list=education_list)
    except Exception:
        logger.warning(
            '[ERROR] SUBJECT_PARAMETER_CROSS(%s): cache_key=%s, locals=%s\n %s' % (
                self.request.id, cache_key, str(locals()), traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_subject_parameter_cross', cache_key, locals(), traceback.format_exc())
    logger.info('[ END ] SUBJECT_PARAMETER_CROSS(%s)' % self.request.id)


def do_statistics_subject_cross(cache_key, main_dimension_code, second_dimension_code, m_city_code_list,
                                province_code_list, city_code_list, gender_list, age_group_list,
                                education_list):
    """

    :param cache_key:
    :param main_dimension_code:
    :param second_dimension_code:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    main_dimension = SubjectDimension.sync_find_one(
        dict(code=main_dimension_code, status=STATUS_SUBJECT_DIMENSION_ACTIVE))
    main_sub_dimension_list = SubjectDimension.sync_find(dict(parent_cid=main_dimension.cid)).sort(
        [('ordered', ASC)]).to_list(None)

    second_dimension = SubjectDimension.sync_find_one(
        dict(code=second_dimension_code, status=STATUS_SUBJECT_DIMENSION_ACTIVE))
    second_sub_dimension_list = SubjectDimension.sync_find(dict(parent_cid=second_dimension.cid)).sort(
        [('ordered', ASC)]).to_list(None)

    data = []
    for index, m_dimen in enumerate(main_sub_dimension_list):
        sub_data_list = []
        for s_dimen in second_sub_dimension_list:
            stage_list = []
            #  取前一天凌晨12点之前的数据
            time_match = get_yesterday()
            stage_list.append(MatchStage({'updated_dt': {'$lt': time_match}}))
            match_dict = {'dimension.%s' % main_dimension.cid: m_dimen.cid,
                          'dimension.%s' % second_dimension.cid: s_dimen.cid}
            if m_city_code_list:
                match_dict['city_code'] = {'$in': m_city_code_list}
            stage_list.append(MatchStage(match_dict))

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
            # 分组
            group_params = {
                'total': {'$sum': '$total'},
                'correct': {'$sum': '$correct'}
            }
            stage_list.append(GroupStage(None, **group_params))

            stat_result = MemberSubjectStatistics.sync_aggregate(
                stage_list).to_list(None)
            tmp_data = {
                'code': s_dimen.code,
                'title': s_dimen.title,
                'ordered': s_dimen.ordered,
                'correct': stat_result[0].correct if stat_result else 0,
                'total': stat_result[0].total if stat_result else 0
            }
            sub_data_list.append(tmp_data)
        main_data = {
            'code': str(index + 1),
            'title': m_dimen.title,
            'ordered': index + 1,
            'sub': sub_data_list
        }
        data.append(main_data)

    if data:
        data.sort(key=lambda x: x.get('ordered', 0))
    if not data:
        early_warning_empty("start_statistics_subject_parameter_cross", cache_key, locals(), '获取维度正确率统计数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))
