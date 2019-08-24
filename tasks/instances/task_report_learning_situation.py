"""
学习效果
"""
import datetime
import json
import traceback

import msgpack

import settings
from commons.common_utils import datetime2str
from db import STATUS_SUBJECT_DIMENSION_ACTIVE
from db.models import MemberDailyDimensionStatistics, MemberLearningDayDimensionStatistics, MemberDailyStatistics, \
    MemberLearningDayStatistics, AdministrativeDivision, SubjectDimension, Member, MemberGameHistory, \
    MemberCheckPointHistory
from enums import KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine import RedisCache, ASC, DESC
from motorengine.stages import MatchStage, SortStage, LimitStage, LookupStage, ProjectStage
from motorengine.stages.group_stage import GroupStage
from services.email_service import send_instant_mail
from tasks import app
from tasks.instances.task_report_learning_member_quantity import early_warning
from tasks.instances.utils import early_warning_empty
from tasks.utils import save_cache_condition, get_yesterday

logger = log_utils.get_logging('task_report_learning_situation', 'task_report_learning_situation.log')


@app.task(bind=True, queue='learning_situation')
def start_statistics_learning_situation(self, cache_key, chart_type=None, m_city_code_list=None, gender_list=None,
                                        province_code_list=None, city_code_list=None, age_group_list=None,
                                        education_list=None, dimension=None, time_range=None, dimension_code=None):
    """
    学习效果任务LEARNING_SITUATION_STATISTICS
    :param self:
    :param cache_key:
    :param chart_type:
    :param m_city_code_list:
    :param gender_list:
    :param province_code_list:
    :param city_code_list:
    :param age_group_list:
    :param education_list:
    :param dimension:
    :param time_range:
    :param dimension_code:
    :return:
    """

    logger.info('[START] LEARNING_SITUATION_STATISTICS(%s), cache_key=%s' % (self.request.id, cache_key))
    try:
        save_cache_condition('start_statistics_learning_situation', cache_key=cache_key, chart_type=chart_type,
                             m_city_code_list=m_city_code_list, gender_list=gender_list,
                             province_code_list=province_code_list, city_code_list=city_code_list,
                             age_group_list=age_group_list, education_list=education_list, dimension=dimension,
                             time_range=time_range, dimension_code=dimension_code)
        do_statistics_learning_situation(cache_key=cache_key, chart_type=chart_type, m_city_code_list=m_city_code_list,
                                         gender_list=gender_list, province_code_list=province_code_list,
                                         city_code_list=city_code_list, age_group_list=age_group_list,
                                         education_list=education_list, dimension=dimension, time_range=time_range,
                                         dimension_code=dimension_code)
    except Exception:
        logger.error('[ERROR] locals_variable: %s \n %s' % (str(locals()), traceback.format_exc()))
        content = 'host=%s,[ERROR] LEARNING_SITUATION_STATISTICS(%s), time=%s,locals_variable: %s \n %s' % (
            settings.SERVER_HOST,
            self.request.id, datetime2str(datetime.datetime.now()), str(locals()), traceback.format_exc())

        send_instant_mail(mail_to=['lf.weng@idiaoyan.com', 'yan.zhan@idiaoyan.com'], subject='学习效果报表任务失败',
                          content=content)
    logger.info('[ END ] LEARNING_SITUATION_STATISTICS(%s)' % self.request.id)


def do_statistics_learning_situation(cache_key, chart_type=None, m_city_code_list=None, gender_list=None,
                                     province_code_list=None, city_code_list=None, age_group_list=None,
                                     education_list=None, dimension=None, time_range=None, dimension_code=None):
    """

    :param cache_key:
    :param chart_type:
    :param m_city_code_list:
    :param gender_list:
    :param province_code_list:
    :param city_code_list:
    :param age_group_list:
    :param education_list:
    :param dimension:
    :param time_range:
    :param dimension_code:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    stage_list = []
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    stage_list.append(MatchStage({'created_dt': {'$lt': time_match}}))
    s_code, e_code = '', ''
    if chart_type == 1:
        s_code, e_code = get_daily_code_range(time_range)

    if city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': m_city_code_list}}))

    parent_dimension_cid, dimension_cid = get_dimension(dimension_code)
    if parent_dimension_cid and dimension_cid:
        stage_list.append(MatchStage({'dimension.%s' % parent_dimension_cid: dimension_cid}))

    query_dict = {}
    if s_code and e_code:
        query_dict['daily_code'] = {'$gte': s_code, '$lte': e_code}
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
    if dimension:
        try:
            s_dimension = json.loads(dimension)
            for k, v in s_dimension.items():
                query_dict['dimension.%s' % k] = {'$in': v}
        except Exception:
            pass
    if query_dict:
        stage_list.append(MatchStage(query_dict))

    stage_list.append(GroupStage('daily_code' if chart_type == 1 else 'learning_code',
                                 total={'$sum': '$subject_total_quantity'},
                                 correct={'$sum': '$subject_correct_quantity'}))
    stage_list.append(SortStage([('_id', ASC)]))
    if chart_type == 2:
        stage_list.append(MatchStage({'_id': {'$lte': 20}}))

    data = []
    # 检索数据
    if chart_type == 1:
        stat_cursor = MemberDailyDimensionStatistics.sync_aggregate(stage_list)
    else:
        stat_cursor = MemberLearningDayDimensionStatistics.sync_aggregate(stage_list)

    while True:
        try:
            md_stat = stat_cursor.next()
            if md_stat:
                data.append({
                    md_stat.id[:8] if chart_type == 1 else md_stat.id: {
                        'total': md_stat.total,
                        'correct': md_stat.correct
                    }
                })
        except StopIteration:
            break
    if not data:
        early_warning_empty("start_statistics_learning_situation", cache_key, locals(), '学习效果中数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))


def get_daily_code_range(time_range):
    """时间区间 3D, 7D, 1M, 3M, 6M, 1Y, 5Y"""
    if time_range:

        suffix = time_range[-1:]
        range_num = int(time_range.replace(suffix, ''))

        delta = None
        if suffix.upper() == 'D':
            delta = datetime.timedelta(days=range_num)
        elif suffix.upper() == 'M':
            delta = datetime.timedelta(days=range_num * 30)
        elif suffix.upper() == 'Y':
            delta = datetime.timedelta(days=range_num * 365)

        if delta:
            return get_daily_code(datetime.datetime.now() - delta), get_daily_code(
                datetime.datetime.now())
    return None, None


def get_daily_code(dt):
    """
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d000000')


def get_dimension(dimension_code):
    """学习效果-答题正确率趋势-{维度}

    :param dimension_code: 形如'CSK001,1'
    :return:
    """
    if dimension_code:
        dimension_code, sub_dimension_code = dimension_code.split(',')
        dimension = SubjectDimension.sync_find_one({
            'code': dimension_code.strip(),
            'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
            'parent_cid': None
        })

        sub_dimension = SubjectDimension.sync_find_one({
            'code': sub_dimension_code.strip(),
            'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
            'parent_cid': dimension.cid
        })

        return sub_dimension.parent_cid, sub_dimension.cid
    return None, None


@app.task(bind=True, queue='quiz_trends')
def start_statistics_quiz_trends(self, cache_key, stat_type, m_city_code_list, province_code_list, city_code_list,
                                 gender_list, age_group_list, education_list, time_range):
    """
    公民科学素质学习答题趋势统计
    :param self:
    :param cache_key:
    :param stat_type:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :param time_range:
    :return:
    """

    logger.info('[START] REPORT_QUIZ_TRENDS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        province_code_list = list(map(lambda x: int(x), province_code_list))
        city_code_list = list(map(lambda x: int(x), city_code_list))
        gender_list = list(map(lambda x: int(x), gender_list))
        age_group_list = list(map(lambda x: int(x), age_group_list))
        education_list = list(map(lambda x: int(x), education_list))

        save_cache_condition('start_statistics_quiz_trends', cache_key=cache_key, stat_type=stat_type,
                             m_city_code_list=m_city_code_list, province_code_list=province_code_list,
                             city_code_list=city_code_list, gender_list=gender_list, age_group_list=age_group_list,
                             education_list=education_list, time_range=time_range)
        do_statistics_quiz_trends(cache_key, stat_type, m_city_code_list, province_code_list, city_code_list,
                                  gender_list, age_group_list, education_list, time_range)
    except Exception:
        logger.warning(
            '[ERROR] REPORT_QUIZ_TRENDS(%s): cache_key=%s, locals=%s, \n %s' % (
                self.request.id, cache_key, str(locals()), traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_quiz_trends', cache_key, locals(), traceback.format_exc())
    logger.info('[ END ] REPORT_QUIZ_TRENDS(%s)' % self.request.id)


def do_statistics_quiz_trends(cache_key, stat_type, m_city_code_list, province_code_list, city_code_list, gender_list,
                              age_group_list, education_list, time_range):
    """

    :param cache_key:
    :param stat_type:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :param time_range:
    :return:
    """

    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 20 * 60)

    basic_stages = []
    if m_city_code_list:
        basic_stages.append(MatchStage({'city_code': {'$in': m_city_code_list}}))
    if province_code_list:
        basic_stages.append(MatchStage({'province_code': {'$in': province_code_list}}))
    if city_code_list:
        basic_stages.append(MatchStage({'city_code': {'$in': city_code_list}}))
    if gender_list:
        basic_stages.append(MatchStage({'sex': {"$in": gender_list}}))
    if age_group_list:
        basic_stages.append(MatchStage({'age_group': {'$in': age_group_list}}))
    if education_list:
        basic_stages.append(MatchStage({'education': {'$in': education_list}}))

    yesterday = get_yesterday()
    time_match = MatchStage({'created_dt': {'$lte': yesterday}})
    if time_range:
        suffix = time_range[-1:]
        range_num = int(time_range.replace(suffix, ''))

        delta = None
        if suffix.upper() == 'D':
            delta = datetime.timedelta(days=range_num)
        elif suffix.upper() == 'M':
            delta = datetime.timedelta(days=range_num * 30)
        elif suffix.upper() == 'Y':
            delta = datetime.timedelta(days=range_num * 365)
        start_dt = yesterday - delta
        time_match = MatchStage({'created_dt': {'$gt': start_dt, '$lt': yesterday}})

    data = []
    game_data = do_stat_in_history(MemberGameHistory, time_match, basic_stages, stat_type)
    ckpt_data = do_stat_in_history(MemberCheckPointHistory, time_match, basic_stages, stat_type)

    for k, v in game_data.items():
        try:
            ckpt_data[k] += v
        except KeyError:
            ckpt_data[k] = v
        data.append({k: ckpt_data[k]})
    if not data:
        early_warning_empty("start_statistics_quiz_trends", cache_key, locals(), '答题趋势统计数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))


def do_stat_in_history(history_model, time_match, basic_stages, stat_type):
    """

    :param history_model:
    :param time_match
    :param basic_stages:
    :param stat_type:
    :return:
    """

    stage_list = [
        time_match,
        ProjectStage(**{
            'daily_code': {'$dateToString': {'format': "%Y%m%d", "date": "$updated_dt"}},
            'member_cid': "$member_cid",
            'updated_dt': '$updated_dt'
        }),
        GroupStage({'member_cid': '$member_cid', 'daily_code': '$daily_code'}, quantity={"$sum": 1},
                   updated_dt={'$first': "$updated_dt"}),
        LookupStage(Member, '_id.member_cid', 'cid', 'member_list'),
        MatchStage({'member_list': {'$ne': []}}),
        ProjectStage(**{
            'daily_code': '$_id.daily_code',
            'member_cid': '$_id.member_cid',
            'updated_dt': '$updated_dt',
            'quantity': '$quantity',
            'city_code': {'$arrayElemAt': ['$member_list.city_code', 0]},
            'province_code': {'$arrayElemAt': ['$member_list.province_code', 0]},
            'sex': {'$arrayElemAt': ['$member_list.sex', 0]},
            'age_group': {'$arrayElemAt': ['$member_list.age_group', 0]},
            'education': {'$arrayElemAt': ['$member_list.education', 0]},
        }),

    ]

    if basic_stages:
        stage_list.extend(basic_stages)

    if stat_type == 'time':
        quantity = {'$sum': "$quantity"}
    else:
        quantity = {'$sum': 1}

    stage_list.extend([
        GroupStage('daily_code', quantity=quantity),
        SortStage([('_id', ASC)])
    ])
    cursor = history_model.sync_aggregate(stage_list, allowDiskUse=True)

    data = {}
    while True:
        try:
            his = cursor.next()

            data[his.id] = his.quantity
        except StopIteration:
            break
        except Exception as e:
            logger.error(str(e))
            continue

    return data


@app.task(bind=True, queue='member_active')
def start_statistics_member_active(self, cache_key, m_city_code_list, province_code_list, city_code_list,
                                   gender_list, age_group_list, education_list):
    """
    公民科学素质学习答题活跃度
    :param self:
    :param cache_key:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """

    logger.info('[START] REPORT_MEMBER_ACTIVE(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_member_active', cache_key=cache_key, m_city_code_list=m_city_code_list,
                             province_code_list=province_code_list, city_code_list=city_code_list,
                             gender_list=gender_list, age_group_list=age_group_list, education_list=education_list)
        do_statistics_member_active(cache_key=cache_key, m_city_code_list=m_city_code_list,
                                    province_code_list=province_code_list, city_code_list=city_code_list,
                                    gender_list=gender_list, age_group_list=age_group_list,
                                    education_list=education_list)
    except Exception:
        logger.warning(
            '[ERROR] REPORT_MEMBER_ACTIVE(%s): cache_key=%s, locals=%s, \n %s' % (
                self.request.id, cache_key, str(locals()), traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_member_active', cache_key, locals(), traceback.format_exc())
    logger.info('[ END ] REPORT_MEMBER_ACTIVE(%s)' % self.request.id)


def do_statistics_member_active(cache_key, m_city_code_list, province_code_list, city_code_list, gender_list,
                                age_group_list, education_list):
    """

    :param cache_key:
    :param m_city_code_list:
    :param province_code_list:
    :param city_code_list:
    :param gender_list:
    :param age_group_list:
    :param education_list:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    # 统计数据
    stage_list = []

    if m_city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': m_city_code_list}}))
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    stage_list.append(MatchStage({'updated_dt': {'$lt': time_match}}))
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

    stage_list.extend([
        GroupStage('learning_code', quantity={'$sum': 1}),
        SortStage([('_id', ASC)]),
        LimitStage(8)
    ])

    mld_stat_cursor = MemberLearningDayStatistics.sync_aggregate(stage_list)
    data = []
    while True:
        try:
            mld_stat = mld_stat_cursor.next()
            if mld_stat:
                data.append({
                    'days': mld_stat.id,
                    'quantity': mld_stat.quantity
                })
        except StopIteration:
            break

    all_members = sum([d.get('quantity') for d in data])
    data_dict = {
        'data_list': data,
        'all_members': all_members
    }
    if not data_dict:
        early_warning_empty("start_statistics_member_active", cache_key, locals(), '答题活跃度统计数据为空，请检查！')

    RedisCache.set(cache_key, msgpack.packb(data_dict))


@app.task(bind=True, queue='member_top_n')
def start_statistics_member_top_n(self, cache_key=None, m_city_code_list=None, stat_type=None, top_n=None,
                                  time_range=None):
    """
    每日参与TOP 5

    :param self:
    :param cache_key:
    :param m_city_code_list:
    :param stat_type:
    :param top_n:
    :param time_range:
    :return:
    """
    logger.info('[START] REPORT_MEMBER_TOP_N(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_member_top_n', cache_key=cache_key, m_city_code_list=m_city_code_list,
                             stat_type=stat_type, top_n=top_n, time_range=time_range)
        do_statistics_member_top_n(cache_key=cache_key, m_city_code_list=m_city_code_list, stat_type=stat_type,
                                   top_n=top_n, time_range=time_range)
    except Exception:
        logger.warning(
            '[ERROR] REPORT_MEMBER_TOP_N(%s): cache_key=%s, locals=%s, \n %s' % (
                self.request.id, cache_key, str(locals()), traceback.format_exc()))
        early_warning(self.request.id, 'start_statistics_member_top_n', cache_key, locals(), traceback.format_exc())
    logger.info('[ END ] REPORT_MEMBER_TOP_N(%s)' % self.request.id)


def do_statistics_member_top_n(cache_key, m_city_code_list, stat_type, top_n, time_range):
    """

    :param cache_key:
    :param m_city_code_list:
    :param stat_type:
    :param top_n:
    :param time_range:
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
    stage_list = []
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    stage_list.append(MatchStage({'updated_dt': {'$lt': time_match}}))
    if m_city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': m_city_code_list}}))
    s_code = ''
    e_code = ''
    if time_range:
        suffix = time_range[-1:]
        range_num = int(time_range.replace(suffix, ''))

        delta = None
        if suffix.upper() == 'D':
            delta = datetime.timedelta(days=range_num)
        elif suffix.upper() == 'M':
            delta = datetime.timedelta(days=range_num * 30)
        elif suffix.upper() == 'Y':
            delta = datetime.timedelta(days=range_num * 365)
        if delta:
            s_code = datetime2str(datetime.datetime.now() - delta, date_format='%Y%m%d000000')
            e_code = datetime2str(datetime.datetime.now(), date_format='%Y%m%d000000')
    if s_code and e_code:
        stage_list.append(MatchStage({'daily_code': {'$gte': s_code, '$lte': e_code}}))

    stage_list.extend([
        GroupStage(
            {
                'daily_code': '$daily_code',
                'member_cid': '$member_cid',
                'province_code': '$province_code'
            } if stat_type == 1 else {
                'daily_code': '$daily_code',
                'member_cid': '$member_cid',
                'province_code': '$province_code',
                'city_code': '$city_code'
            },
            learn_times={'$sum': '$learn_times'}),
        GroupStage(
            {
                'daily_code': '$_id.daily_code',
                'province_code': '$_id.province_code'
            } if stat_type == 1 else {
                'daily_code': '$_id.daily_code',
                'province_code': '$_id.province_code',
                'city_code': '$_id.city_code'
            },
            count={'$sum': 1}, times={'$sum': '$learn_times'}),
        LookupStage(AdministrativeDivision, '_id.province_code', 'post_code', 'province_list'),
        LookupStage(AdministrativeDivision, '_id.city_code', 'post_code', 'city_list'),
        ProjectStage(**{
            '_id': False,
            'daily_code': '$_id.daily_code',
            'count': '$count',
            'times': '$times',
            'province_code': '$_id.province_code',
            'province_title': '$province_list.title',
            'ad_code': '$_id.province_code' if stat_type == 1 else '$_id.city_code',
            'ad_title': '$province_list.title' if stat_type == 1 else '$city_list.title'
        }),
        SortStage([('daily_code', ASC), ('count', DESC)])
    ])
    # 检索数据
    data = []
    stat_cursor = MemberDailyStatistics.sync_aggregate(stage_list)
    t_code, t_list = None, None
    top_n_found = False
    while True:
        try:
            daily_stat = stat_cursor.next()
            if daily_stat:
                daily_code = daily_stat.daily_code
                if not daily_code == t_code:
                    t_code = daily_code
                    t_list = []
                    top_n_found = False
                    print(t_code)
                if len(t_list) < top_n:
                    t_list.append({
                        'date': daily_code[:8],
                        'ad_code': daily_stat.ad_code,
                        'province_title': daily_stat.province_title[
                            0] if daily_stat.province_title and stat_type == 2 else '',
                        'title': daily_stat.ad_title[0] if daily_stat.ad_title else 'undefined',
                        'quantity': daily_stat.count,
                        'times': daily_stat.times
                    })
                elif not top_n_found:
                    if t_code is not None:
                        data.append(t_list)
                    top_n_found = True
        except StopIteration:
            break
    if not data:
        early_warning_empty("start_statistics_member_top_n", cache_key, locals(), '每日参与TOP5统计数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))

#
# def do_statistics_member_top_n_both(cache_key):  # , m_city_code_list, stat_type, top_n, s_code, e_code):
#     """
#     从学习之旅数据和竞赛数据中统计
#     :param cache_key:
#     :param m_city_code_list:
#     :param stat_type:
#     :param top_n:
#     :param s_code:
#     :param e_code:
#     :return:
#     """
#     # RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)
#     stage_list = []
#     # #  取前一天凌晨12点之前的数据
#     # time_match = get_yesterday()
#     # stage_list.append(MatchStage({'created_dt': {'$lt': time_match}}))
#
#     stage_list.extend([
#         LookupStage(Member, 'member_cid', 'cid', 'member_list'),
#         MatchStage({"member_list": {"$ne": []}}),
#         ProjectStage(**{
#             'daily_code': {"$dateToString": {"format": "%Y%m%d", "date": "$created_dt"}},
#             'member_cid': 1,
#             'province_code': {"$arrayElemAt": ["$member_list.province_code", 0]},
#             'city_code': {"$arrayElemAt": ["$member_list.city_code", 0]},
#         }),
#         GroupStage({'daily_code': '$daily_code', 'member_cid': '$member_cid'},
#                    member_times={'$sum': 1}, province_code={"$first": "$province_code"},
#                    city_code={"$first": "$city_code"}),
#         GroupStage({'daily_code': '$_id.daily_code', 'city_code': '$city_code'},
#                    province_code={"$first": "$province_code"}, member_times={"$sum": "$member_times"},
#                    member_count={"$sum": 1}),
#         SortStage([('_id.daily_code', ASC), ('member_times', DESC)])
#     ])
#     MemberGameHistory.aggregate(stage_list)
