import traceback

from commons.common_utils import RedisCache
from db import STATUS_SUBJECT_STATISTICS_IN_PROCESS, STATUS_SUBJECT_STATISTICS_END, STATUS_SUBJECT_INACTIVE, \
    CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION
from db.models import Subject, SubjectOption, MemberSubjectStatistics, ReportSubjectStatisticsMiddle
from enums import KEY_CACHE_REPORT_CONDITION
from logger import log_utils
from motorengine import ASC, DESC
from motorengine.stages import ProjectStage, LookupStage, MatchStage, SortStage, LimitStage, CountStage, SkipStage
from motorengine.stages.group_stage import GroupStage
from pymongo import ReadPreference
from settings import SKIP_NUM
from tasks import app

logger = log_utils.get_logging('task_subject_statistics', 'task_subject_statistics.log')


@app.task(bind=True, queue='subject_stat_split')
def start_split_subject_stat_task(self, category, task_dt):
    """

    :param self:
    :param category:
    :param task_dt:
    :return:
    """
    logger.info('START(%s): Begin split subject_statistics, condition is %s' % (self.request.id, str(category)))

    try:
        result = RedisCache.hget(KEY_CACHE_REPORT_CONDITION, str(category))
        if result is not None:
            logger.warning(
                ' END (%s): DOING or Done split subject_statistics, condition is %s' % (self.request.id, str(category)))
            return

        count_list = MemberSubjectStatistics.sync_aggregate(stage_list=[GroupStage(category), CountStage()]).to_list(1)
        count = count_list[0].count if count_list else 0
        logger.info('request(%s): SPLIT, count=%s' % (self.request.id, count))

        quot, rema = divmod(count, SKIP_NUM)

        ReportSubjectStatisticsMiddle.sync_delete_many({'category': category})
        task_num = quot
        if rema:
            task_num = quot + 1
            start_task_subject_statistics.delay(category, task_dt, quot * SKIP_NUM, self.request.id, task_num)

        for i in range(quot):
            start_task_subject_statistics.delay(category, task_dt, i * SKIP_NUM, self.request.id, task_num)

        RedisCache.hset(KEY_CACHE_REPORT_CONDITION, str(category), STATUS_SUBJECT_STATISTICS_IN_PROCESS)

    except Exception:
        logger.error(traceback.format_exc())

    logger.info(' END (%s): Finish split subject_statistics, condition is %s' % (self.request.id, str(category)))


@app.task(bind=True, queue='subject_statistics')
def start_task_subject_statistics(self, group_dict=None, task_dt=None, skip_num=None, parent_task_id=None,
                                  task_num=None):
    """

    :param self
    :param group_dict:
    :param task_dt:
    :param skip_num:
    :param parent_task_id:
    :param task_num:
    :return:
    """
    try:
        logger.info('START(%s): condition= %s , skip_num=%s, parent_task_id=%s' % (
            self.request.id, str(group_dict), skip_num, parent_task_id))
        middle_list = list()

        logger.info('group_dict: %s' % str(group_dict))

        stages = get_stages(group_dict, skip_num)
        subject_list = MemberSubjectStatistics.sync_aggregate(stage_list=stages, allowDiskUse=True).batch_size(32)

        logger.info('request(%s), aggregate has finished. category is %s' % (self.request.id, str(group_dict)))
        for subject in subject_list:
            mid = ReportSubjectStatisticsMiddle()
            mid.category = group_dict
            mid.condition = subject.id

            mid.custom_code = subject.custom_code
            mid.code = subject.code

            mid.option_dict = {str(opt.sort): {'title': opt.title, 'correct': opt.correct} for opt in
                               subject.option_list}
            mid.dimension = subject.dimension

            mid.title = subject.title
            mid.total = subject.total
            mid.correct = subject.correct
            if task_dt:
                mid.task_dt = task_dt

            middle_list.append(mid)
            if len(middle_list) >= 5000:
                ReportSubjectStatisticsMiddle.sync_insert_many(middle_list)
                middle_list = list()

        if middle_list:
            ReportSubjectStatisticsMiddle.sync_insert_many(middle_list)

        RedisCache.sadd(parent_task_id, self.request.id)
        task_count = get_task_count(parent_task_id)
        if task_count == task_num:
            RedisCache.hset(KEY_CACHE_REPORT_CONDITION, str(group_dict), STATUS_SUBJECT_STATISTICS_END)
            RedisCache.delete(parent_task_id)
        logger.info(' EXEC(%s): %s tasks has finished' % (self.request.id, task_count))
        logger.info(' END (%s), parent_task_id=%s' % (self.request.id, parent_task_id))
    except Exception:
        logger.error(traceback.format_exc())


def get_task_count(request_id):
    """

    :param request_id:
    :return:
    """

    members = RedisCache.smembers(request_id)
    if isinstance(members, (list, set)):
        return len(members)


def get_group_dict(condition_dict=None):
    """

    :param condition_dict:
    :return:
    """
    group_dict = {'subject_cid': '$subject_cid', 'province_code': '$province_code', 'city_code': '$city_code'}
    if condition_dict:
        group_dict.update(condition_dict)

    return group_dict


def get_stages(group_dict=None, skip_num=None):
    """

    :param group_dict:
    :param skip_num:
    :return:
    """
    if not group_dict or skip_num is None:
        logger.error('there is not group_dict(%s) or skip_num(%s)' % (group_dict, skip_num))
        raise ValueError()

    inactive_subject_cids = Subject.sync_distinct('cid',
                                                  {'$or': [
                                                      {'status': STATUS_SUBJECT_INACTIVE},
                                                      {'category_use': {
                                                          '$in': [CATEGORY_SUBJECT_BENCHMARK,
                                                                  CATEGORY_SUBJECT_GRADUATION]}}
                                                  ]})

    inactive_sbj = MatchStage({'subject_cid': {'$nin': inactive_subject_cids}})

    group_stage = GroupStage(group_dict, t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'},
                             created_dt={'$max': '$created_dt'})
    sort_stage = SortStage([('t_total', DESC), ('t_correct', DESC), ('created_dt', ASC)])

    project_stage = ProjectStage(
        total='$t_total', correct='$t_correct',
        percent={
            '$cond': {
                'if': {'$eq': ['$t_total', 0]},
                'then': 0,
                'else': {
                    '$divide': ['$t_correct', '$t_total']
                }
            }
        })
    s_lookup_stage = LookupStage(
        Subject,
        as_list_name='subject_list',
        let={'subject_id': "$_id.subject_cid"},
        pipeline=[
            {
                '$match': {
                    '$expr': {
                        '$and': [
                            {'$eq': ['$cid', '$$subject_id']}
                        ]
                    }
                }
            }
        ]
    )
    so_lookup_stage = LookupStage(
        SubjectOption,
        as_list_name='subject_option_list',
        let={'subject_id': "$_id.subject_cid"},
        pipeline=[
            {
                '$match': {
                    '$expr': {
                        '$and': [
                            {'$eq': ['$subject_cid', '$$subject_id']}
                        ]
                    }
                }
            },
            {
                '$sort': {'code': ASC}
            }
        ]
    )
    match_stage = MatchStage({
        'subject_list': {'$ne': []},
        'subject_option_list': {'$ne': []}
    })
    project_stage2 = ProjectStage(**{
        'custom_code': {'$arrayElemAt': ['$subject_list.custom_code', 0]},
        'code': {'$arrayElemAt': ['$subject_list.code', 0]},
        'title': {'$arrayElemAt': ['$subject_list.title', 0]},
        'option_list': '$subject_option_list',
        'dimension': {'$arrayElemAt': ['$subject_list.dimension_dict', 0]},
        'total': '$total',
        'correct': '$correct'
    })
    skip_stage = SkipStage(skip_num)
    limit_stage = LimitStage(10000)

    return [inactive_sbj, group_stage, sort_stage, skip_stage, limit_stage, project_stage, s_lookup_stage,
            so_lookup_stage, match_stage, project_stage2]


def clear_middle_data():
    RedisCache.delete(KEY_CACHE_REPORT_CONDITION)
    ReportSubjectStatisticsMiddle().get_sync_collection(read_preference=ReadPreference.PRIMARY).drop()


def clear_data_by_category(group_dict):
    """

    :param group_dict:
    :return:
    """
    RedisCache.hset(KEY_CACHE_REPORT_CONDITION, str(group_dict))
    ReportSubjectStatisticsMiddle.sync_delete_many({'category': group_dict})


if __name__ == '__main__':
    clear_middle_data()

    # group_dict = {'subject_cid': '$subject_cid', 'province_code': '$province_code', 'city_code': '$city_code',
    #               'age_group': '$age_group', 'gender': '$gender'}
    # stages = get_stages(group_dict, skip_num=0)
    # subject_list = MemberSubjectStatistics.sync_aggregate(stage_list=stages, allowDiskUse=True).batch_size(32)
    # stage_list = get_stages({
    #     "subject_cid": "$subject_cid",
    #     "province_code": "$province_code",
    #     "city_code": "$city_code"
    # }, 0)
    #
    # MemberSubjectStatistics.aggregate(stage_list)
