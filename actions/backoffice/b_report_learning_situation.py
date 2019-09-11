# !/usr/bin/python
# -*- coding:utf-8 -*-


import copy
import datetime
import json
import traceback

import msgpack
from tornado.web import url

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str, str2datetime, md5
from db import STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_USER_ACTIVE
from db.model_utils import do_different_administrative_division2, do_different_administrative_division
from db.models import AdministrativeDivision, SubjectDimension, Member, \
    MemberPropertyStatistics
from enums import PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT, \
    PERMISSION_TYPE_REPORT_LEARNING_TENDENCY_MANAGEMENT, PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT, \
    KEY_CACHE_REPORT_DOING_NOW
from logger import log_utils
from motorengine import DESC, FacadeO, ASC
from motorengine.stages import LookupStage, SortStage, MatchStage, LimitStage
from motorengine.stages.group_stage import GroupStage
from tasks.instances.task_report_learning_member_quantity import start_statistics_member_quantity, \
    start_statistics_member_accuracy, start_statistics_member_time
from tasks.instances.task_report_learning_situation import start_statistics_learning_situation, \
    start_statistics_quiz_trends, start_statistics_member_active, start_statistics_member_top_n
from tasks.instances.task_report_subject_parameter import start_statistics_subject_quantity
from web import BaseHandler, decorators

logger = log_utils.get_logging()
logger_cache = log_utils.get_logging('cache')


class ReportLearningSituationViewHandler(BaseHandler):
    """
    学习状况
    """

    @decorators.render_template('backoffice/reports/learning_situation_view.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def get(self):
        dark_skin = self.get_argument('dark_skin')
        dark_skin = True if dark_skin == 'True' else False
        region_code_list = []
        manage_region_code_list = self.current_user.manage_region_code_list
        ad_cursor = AdministrativeDivision.find({'code': {'$in': self.current_user.manage_region_code_list}})
        while await ad_cursor.fetch_next:
            ad = ad_cursor.next_object()
            if ad:
                if ad.level == 'P':
                    region_code_list.append('[p]%s' % ad.code)
                elif ad.level == 'C':
                    region_code_list.append('[c]%s' % ad.code)
                elif ad.level == 'D':
                    region_code_list.append('[d]%s' % ad.code)

        region_name = await self.parse_region_name()
        return locals()

    async def parse_region_name(self):
        """
        解析下钻的地图
        :return:
        """
        prov_code_list = []

        try:
            for code in self.current_user.manage_region_code_list:
                if code[:-4] == '0000':
                    prov_code_list.append(code)
                else:
                    prov_code = code[:2] + '0000'
                    if prov_code not in prov_code_list:
                        prov_code_list.append(prov_code)

            if len(prov_code_list) == 1:
                ad = await AdministrativeDivision.find_one({'code': prov_code_list[0]})
                return ad.title.replace('省', '')
        except Exception:
            pass

        return


class ReportLearningSituationCumulativeViewHandler(BaseHandler):
    """
    获取公民参与学习累计图表信息（地图 & 排行）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list, city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            choice_time = self.get_argument('choice_time', '')
            choice_time = str2datetime(choice_time) if choice_time else ''
            city_code_list.sort(key=str)
            province_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LEARNING_TIMES_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              choice_time=choice_time if choice_time else None)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if data is None:
                start_statistics_member_time.delay(cache_key, city_code_list, choice_time)
                result['cache_key'] = cache_key
                result['code'] = 2
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationMemberQuantityViewHandler(BaseHandler):
    """
    获取公民参与学习累计图表人数信息（地图 & 排行）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list, city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            choice_time = self.get_argument('choice_time', '')
            choice_time = str2datetime(choice_time) if choice_time else ''
            city_code_list.sort(key=str)
            province_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LS_MEMBER_QUANTITY_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              choice_time=choice_time if choice_time else None)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if data is None:
                start_statistics_member_quantity.delay(cache_key, city_code_list, choice_time)
                result['cache_key'] = cache_key
                result['code'] = 2
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationAccuracyViewHandler(BaseHandler):
    """
    获取公民参与学习累计正确率信息（地图 & 排行）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            _, city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            choice_time = self.get_argument('choice_time', '')
            choice_time = str2datetime(choice_time) if choice_time else ''
            # 每个传过来得city_code_list，元素位置不同， 导致产生得cache_key不同，所以得固定位置
            city_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LEARNING_ACCURACY_STATISTIC', city_code_list=city_code_list,
                                              choice_time=choice_time if choice_time else None)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if data is None:
                start_statistics_member_accuracy.delay(cache_key, city_code_list, choice_time)
                result['cache_key'] = cache_key
                result['code'] = 2
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationMemberActiveViewHandler(BaseHandler):
    """
    获取公民活跃度（按学习日）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')
            province_code_list.sort(key=str)
            city_code_list.sort(key=str)
            gender_list.sort(key=str)
            age_group_list.sort(key=str)
            education_list.sort(key=str)
            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            m_province_code_list.sort(key=str)
            m_city_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LS_MEMBER_ACTIVE_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              gender_list=gender_list, age_group_list=age_group_list,
                                              education_list=education_list, m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if data is None:
                start_statistics_member_active.delay(cache_key=cache_key, m_city_code_list=m_city_code_list,
                                                     province_code_list=province_code_list,
                                                     city_code_list=city_code_list,
                                                     gender_list=gender_list, age_group_list=age_group_list,
                                                     education_list=education_list)
                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationDailyMemberTimesViewHandler(BaseHandler):
    """
    公民科学素质学习答题趋势统计
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')
            important_crowd_list = self.get_arguments('important_crowd_list[]')
            time_range = self.get_argument('time_range')
            province_code_list.sort(key=str)
            city_code_list.sort(key=str)
            gender_list.sort(key=str)
            age_group_list.sort(key=str)
            education_list.sort(key=str)
            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            m_province_code_list.sort(key=str)
            m_city_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LS_MEMBER_TIMES_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              gender_list=gender_list, age_group_list=age_group_list,
                                              education_list=education_list, time_range=time_range,
                                              m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if not data:
                start_statistics_quiz_trends.delay(cache_key=cache_key, stat_type='time',
                                                   m_city_code_list=m_city_code_list,
                                                   province_code_list=province_code_list, city_code_list=city_code_list,
                                                   gender_list=gender_list, age_group_list=age_group_list,
                                                   education_list=education_list, time_range=time_range)

                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationDailyMemberQuantityViewHandler(BaseHandler):
    """
    获取公民答题人次趋势
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')
            time_range = self.get_argument('time_range')
            province_code_list.sort(key=str)
            city_code_list.sort(key=str)
            gender_list.sort(key=str)
            age_group_list.sort(key=str)
            education_list.sort(key=str)
            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            m_province_code_list.sort(key=str)
            m_city_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LS_DAILY_MEMBER_QUANTITY_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              gender_list=gender_list, age_group_list=age_group_list,
                                              education_list=education_list, time_range=time_range,
                                              m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)

            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if not data:
                start_statistics_quiz_trends.delay(cache_key=cache_key, stat_type='quantity',
                                                   m_city_code_list=m_city_code_list,
                                                   province_code_list=province_code_list, city_code_list=city_code_list,
                                                   gender_list=gender_list, age_group_list=age_group_list,
                                                   education_list=education_list, time_range=time_range)
                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result

    def __get_daily_code_range(self):
        time_range = self.get_argument('time_range')  # 时间区间 3D, 7D, 1M, 3M, 6M, 1Y, 5Y
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
                return self.__get_daily_code(datetime.datetime.now() - delta), self.__get_daily_code(
                    datetime.datetime.now())
        return '', ''

    @staticmethod
    def __get_daily_code(dt):
        """
        获取对接标识
        :return:
        """
        return datetime2str(dt, date_format='%Y%m%d000000')


class ReportLearningSituationMemberIncreaseViewHandler(BaseHandler):
    """
    获取公民答题日新增会员最多的城市排行
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            top_n = int(self.get_argument('top_n', 5))
            date = self.get_argument('date')  # 格式：20180612
            if date:
                province_code_list, city_code_list, _ = await do_different_administrative_division2(
                    self.current_user.manage_region_code_list)
                cache_key = do_generate_cache_key('_RESULT_LT_MEMBER_INCREASE_STATISTIC',
                                                  province_code_list=province_code_list, city_code_list=city_code_list,
                                                  date=date, top_n=top_n)
                data = RedisCache.get(cache_key)
                logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
                if not data:
                    start_datetime = None
                    end_datetime = None
                    try:
                        dt = str2datetime(date, '%Y%m%d')
                        start_datetime = copy.deepcopy(dt).replace(hour=0, minute=0, second=0, microsecond=0)
                        end_datetime = copy.deepcopy(dt).replace(hour=23, minute=59, second=59, microsecond=999999)
                    except ValueError:
                        pass

                    if not start_datetime or not end_datetime:
                        result['code'] = -3  # 时间格式错误
                        return result

                    match_dict = {}
                    or_list, and_list = [], []
                    if province_code_list:
                        or_list.append({'province_code': {'$in': province_code_list}})
                    else:
                        and_list.append({'province_code': {'$ne': None}})
                    if city_code_list:
                        or_list.append({'city_code': {'$in': city_code_list}})
                    else:
                        and_list.append({'city_code': {'$ne': None}})
                    if or_list:
                        match_dict['$or'] = or_list

                    and_list.extend([
                        {'status': STATUS_USER_ACTIVE},
                        {'created_dt': {'$gte': start_datetime, '$lte': end_datetime}}
                    ])
                    match_dict['$and'] = and_list

                    match_stage = MatchStage(match_dict)
                    group_stage = GroupStage(
                        {'province_code': '$province_code', 'city_code': '$city_code'}, quantity={'$sum': 1})
                    limit_stage = LimitStage(top_n)
                    sort_stage = SortStage([('quantity', DESC), ('_id', ASC)])
                    p_lookup_stage = LookupStage(
                        AdministrativeDivision, '_id.province_code', 'post_code', 'province_list')
                    c_lookup_stage = LookupStage(AdministrativeDivision, '_id.city_code', 'post_code', 'city_list')
                    # 检索数据
                    data = []
                    member_cursor = Member.aggregate([
                        match_stage, group_stage, sort_stage, limit_stage, p_lookup_stage, c_lookup_stage])
                    while await member_cursor.fetch_next:
                        member = member_cursor.next_object()
                        if member:
                            city_code = '000000'
                            city_name = 'undefined'
                            province_code = '000000'
                            province_name = 'undefined'
                            city_list = member.city_list
                            if city_list:
                                ad: FacadeO = city_list[0]
                                if ad:
                                    city_code = ad.post_code
                                    city_name = ad.title
                            province_list = member.province_list
                            if province_list:
                                ad: FacadeO = province_list[0]
                                if ad:
                                    province_code = ad.post_code
                                    province_name = ad.title
                            data.append({
                                'code': city_code,
                                'title': city_name,
                                'province_code': province_code,
                                'province_title': province_name,
                                'quantity': member.quantity
                            })
                    RedisCache.set(cache_key, msgpack.packb(data), 10 * 60)
                    result['data'] = data
                    result['code'] = 1
                else:
                    result['data'] = msgpack.unpackb(data, raw=False)
                    result['code'] = 1
            else:
                result['code'] = -1  # 时间为空
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningSituationDailyMemberQuantityTopViewHandler(BaseHandler):
    """
    获取公民答题日新增会员最多的城市排行
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            top_n = int(self.get_argument('top_n', 5))

            time_range = self.get_argument('time_range', '')
            stat_type = int(self.get_argument('stat_type', 2))  # 1: 省份， 2: 城市
            stat_category = int(self.get_argument('stat_category', 1))  # 1: 人数， 2: 次数
            _, city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)
            city_code_list.sort(key=str)
            cache_key = do_generate_cache_key('_RESULT_LS_DAILY_MEMBER_QUANTITY_TOP_STATISTIC',
                                              city_code_list=city_code_list, stat_type=stat_type,
                                              stat_category=stat_category, top_n=top_n, time_range=time_range)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if not data:
                start_statistics_member_top_n.delay(cache_key=cache_key, m_city_code_list=city_code_list,
                                                    stat_type=stat_type, top_n=top_n, time_range=time_range)
                result['cache_key'] = cache_key
                result['code'] = 2
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningTendencyViewHandler(BaseHandler):
    """
    学习趋势
    """

    @decorators.render_template('backoffice/reports/learning_tendency_view.html')
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_TENDENCY_MANAGEMENT)
    async def get(self):
        dark_skin = self.get_argument('dark_skin')
        dark_skin = True if dark_skin == 'True' else False
        switch_type = self.get_argument('switch_type', 2)
        time_range = self.get_argument('time_range', '6M')

        region_code_list = []
        manage_region_code_list = self.current_user.manage_region_code_list
        ad_cursor = AdministrativeDivision.find({'code': {'$in': self.current_user.manage_region_code_list}})
        while await ad_cursor.fetch_next:
            ad = ad_cursor.next_object()
            if ad:
                if ad.level == 'P':
                    region_code_list.append('[p]%s' % ad.code)
                elif ad.level == 'C':
                    region_code_list.append('[c]%s' % ad.code)
                elif ad.level == 'D':
                    region_code_list.append('[d]%s' % ad.code)
        subject_dimension_list = await SubjectDimension.aggregate(
            [MatchStage(dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)),
             LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_subject_dimension_list')]).to_list(None)
        return locals()


class ReportLearningTendencySubjectQuantityViewHandler(BaseHandler):
    """
    获取公民答对题目数量分布
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_SUBJECT_PARAMETER_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')

            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)

            cache_key = do_generate_cache_key('_RESULT_LT_SUBJECT_QUANTITY_STATISTIC',
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              gender_list=gender_list, age_group_list=age_group_list,
                                              education_list=education_list, m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if data is None:
                start_statistics_subject_quantity.delay(cache_key, m_province_code_list, m_city_code_list,
                                                        province_code_list, city_code_list, gender_list, age_group_list,
                                                        education_list)
                result['code'] = 2
                result['cache_key'] = cache_key
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': {}}
        except Exception:
            logger.error(traceback.format_exc())

        return result


class ReportLearningTendencyAccuracyViewHandler(BaseHandler):
    """
    获取公民答题正确率趋势(学习效果报表）
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_TENDENCY_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            chart_type = int(self.get_argument('chart_type', 1))  # 1： 按自然日， 2： 按学习日
            province_code_list = self.get_arguments('province_code_list[]')
            city_code_list = self.get_arguments('city_code_list[]')
            gender_list = self.get_arguments('gender_list[]')
            age_group_list = self.get_arguments('age_group_list[]')
            education_list = self.get_arguments('education_list[]')
            dimension = self.get_argument('dimension', '')
            time_range = self.get_argument('time_range')
            dimension_code = self.get_argument('dimension_code', '')  # 形如： 'CSK001,1'

            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                self.current_user.manage_region_code_list)

            cache_key = do_generate_cache_key('_RESULT_LT_ACCURACY_STATISTIC', chart_type=chart_type,
                                              m_city_code_list=m_city_code_list, gender_list=gender_list,
                                              province_code_list=province_code_list, city_code_list=city_code_list,
                                              age_group_list=age_group_list, education_list=education_list,
                                              dimension=md5(dimension), time_range=time_range,
                                              dimension_code=dimension_code)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if not data:
                start_statistics_learning_situation.delay(cache_key=cache_key, chart_type=chart_type,
                                                          m_city_code_list=m_city_code_list, gender_list=gender_list,
                                                          province_code_list=province_code_list,
                                                          city_code_list=city_code_list, age_group_list=age_group_list,
                                                          education_list=education_list, dimension=dimension,
                                                          time_range=time_range, dimension_code=dimension_code)
                result['cache_key'] = cache_key
                result['code'] = 2
            elif data == KEY_CACHE_REPORT_DOING_NOW:
                result['code'] = 2
                result['cache_key'] = cache_key
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result


class ReportLearningTendencyDimensionAccuracyViewHandler(BaseHandler):
    """（废弃）改用正确率统计
    获取维度正确率趋势
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_TENDENCY_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            dimension_code = self.get_argument('dimension_code', '')  # 形如： 'CSK001,1'
            if dimension_code:
                dimension_code, sub_dimension_code = dimension_code.split(',')
                dimension = await SubjectDimension.find_one({
                    'code': dimension_code.strip(),
                    'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                    'parent_cid': None
                })
                if dimension:
                    sub_dimension = await SubjectDimension.find_one({
                        'code': sub_dimension_code.strip(),
                        'status': STATUS_SUBJECT_DIMENSION_ACTIVE,
                        'parent_cid': dimension.cid
                    })
                    if sub_dimension:
                        chart_type = int(self.get_argument('chart_type', 1))  # 1： 按自然日， 2： 按学习日
                        province_code_list = self.get_arguments('province_code_list[]')
                        city_code_list = self.get_arguments('city_code_list[]')
                        gender_list = self.get_arguments('gender_list[]')
                        age_group_list = self.get_arguments('age_group_list[]')
                        education_list = self.get_arguments('education_list[]')
                        s_dimension = self.get_argument('dimension', '')
                        s_code, e_code = None, None
                        if chart_type == 1:
                            s_code, e_code = self.__get_daily_code_range()

                        m_province_code_list, m_city_code_list, _ = await do_different_administrative_division2(
                            self.current_user.manage_region_code_list)

                        cache_key = do_generate_cache_key('_RESULT_LT_DIMENSION_ACCURACY_STATISTIC',
                                                          dimension_code=dimension_code,
                                                          sub_dimension_code=sub_dimension_code,
                                                          province_code_list=province_code_list,
                                                          city_code_list=city_code_list, gender_list=gender_list,
                                                          age_group_list=age_group_list, education_list=education_list,
                                                          m_province_code_list=m_province_code_list,
                                                          m_city_code_list=m_city_code_list, chart_type=chart_type,
                                                          s_dimension=s_dimension, s_code=s_code, e_code=e_code)
                        data = RedisCache.get(cache_key)
                        logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
                        if not data:
                            # 检索数据
                            stage_list: list = self.merge_search_params(sub_dimension.parent_cid, sub_dimension.cid,
                                                                        m_province_code_list, m_city_code_list)
                            stage_list.append(
                                GroupStage(
                                    'daily_code' if chart_type == 1 else 'learning_code',
                                    total={'$sum': '$subject_total_quantity'},
                                    correct={'$sum': '$subject_correct_quantity'}
                                )
                            )
                            stage_list.append(SortStage([('_id', ASC)]))
                            if not chart_type == 1:
                                stage_list.append(LimitStage(30))
                            pipelines = [stage.to_query() for stage in stage_list]
                            start_statistics_learning_situation.delay(cache_key, pipelines, chart_type)
                            result['cache_key'] = cache_key
                            result['code'] = 2
                            return result
                        elif data == KEY_CACHE_REPORT_DOING_NOW:
                            result['code'] = 2
                            result['cache_key'] = cache_key
                        else:
                            result['data'] = msgpack.unpackb(data, raw=False)
                            result['code'] = 1
                    else:
                        result['code'] = -2  # 维度不存在
                else:
                    result['code'] = -2  # 维度不存在
            else:
                result['code'] = -1  # 没有dimension_code参数
        except ValueError:
            result = {'code': 1, 'data': []}
        except Exception:
            logger.error(traceback.format_exc())
        return result

    def __get_daily_code_range(self):
        time_range = self.get_argument('time_range')  # 时间区间 3D, 7D, 1M, 3M, 6M, 1Y, 5Y
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
                return self.__get_daily_code(datetime.datetime.now() - delta), self.__get_daily_code(
                    datetime.datetime.now())
        return None, None

    @staticmethod
    def __get_daily_code(dt):
        """
        获取对接标识
        :return:
        """
        return datetime2str(dt, date_format='%Y%m%d000000')

    def merge_search_params(self, dimension_cid, sub_dimension_cid, m_province_code_list, m_city_code_list):
        stage_list = []
        if dimension_cid and sub_dimension_cid:
            s_chart_type = int(self.get_argument('chart_type', 1))  # 1： 按自然日， 2： 按学习日
            s_province_code_list = self.get_arguments('province_code_list[]')
            s_city_code_list = self.get_arguments('city_code_list[]')
            s_gender_list = self.get_arguments('gender_list[]')
            s_age_group_list = self.get_arguments('age_group_list[]')
            s_education_list = self.get_arguments('education_list[]')
            s_dimension = self.get_argument('dimension', '')
            s_code, e_code = None, None
            if s_chart_type == 1:
                s_code, e_code = self.__get_daily_code_range()

            match_dict = {}
            if m_province_code_list:
                match_dict['province_code'] = {'$in': m_province_code_list}
            if m_city_code_list:
                match_dict['city_code'] = {'$in': m_city_code_list}

            s_and_list = [{'dimension.%s' % dimension_cid: sub_dimension_cid}]
            if s_code and e_code:
                s_and_list.append({'daily_code': {'$gte': s_code, '$lte': e_code}})
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
            if s_dimension:
                try:
                    s_dimension = json.loads(s_dimension)
                    for k, v in s_dimension.items():
                        s_and_list.append({'dimension.%s' % k: {'$in': v}})
                except Exception:
                    pass
            if s_and_list:
                match_dict['$and'] = s_and_list
            if match_dict:
                stage_list.append(MatchStage(match_dict))

        return stage_list


class ReportLearningTendencyDailyCityMemberTopNViewHandler(BaseHandler):
    """
    每日城市新会员Top N
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_REPORT_LEARNING_SITUATION_MANAGEMENT)
    async def post(self):
        result = {'code': 0}
        try:
            top_n = int(self.get_argument('top_n', 5))
            s_code, e_code = self.__get_daily_code_range()

            m_province_code_list, m_city_code_list, _ = await do_different_administrative_division(
                self.current_user.manage_region_code_list)

            cache_key = do_generate_cache_key('_RESULT_LT_CITY_DAILY_TOP_N_STATISTIC',
                                              m_province_code_list=m_province_code_list,
                                              m_city_code_list=m_city_code_list, s_code=s_code, e_code=e_code,
                                              top_n=top_n)
            data = RedisCache.get(cache_key)
            logger_cache.info('[%s]cache_key: %s' % (self.__class__.__name__, cache_key))
            if not data:
                # 检索数据
                data = []
                stage_list = self.merge_search_params(m_province_code_list, m_city_code_list)
                # 临时存储值
                daily_code, c_data, index = None, None, 0
                stat_cursor = MemberPropertyStatistics.aggregate(stage_list)
                while await stat_cursor.fetch_next:
                    mp_stat = stat_cursor.next_object()
                    if mp_stat:
                        t_daily_code = mp_stat.id.get('daily_code')
                        if t_daily_code:
                            if not t_daily_code == daily_code:
                                if c_data is not None:
                                    data.append({daily_code: c_data})
                                daily_code = t_daily_code
                                c_data = []
                                index = 0
                            if index < top_n:
                                t_city_title = ''
                                if mp_stat.city_list:
                                    city = mp_stat.city_list[0]
                                    if city:
                                        t_city_title = city.title
                                t_city_code = mp_stat.id.get('city_code')
                                c_data.append({
                                    'city_code': t_city_code,
                                    'city_name': t_city_title,
                                    'quantity': mp_stat.quantity
                                })
                        index += 1
                result['data'] = data
                result['code'] = 1
                RedisCache.set(cache_key, msgpack.packb(data), 10 * 60)
            else:
                result['data'] = msgpack.unpackb(data, raw=False)
                result['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return result

    def __get_daily_code_range(self):

        time_range = self.get_argument('time_range')  # 时间区间 3D, 7D, 1M, 3M, 6M, 1Y, 5Y
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
                return self.__get_daily_code(datetime.datetime.now() - delta), self.__get_daily_code(
                    datetime.datetime.now())
        return '', ''

    @staticmethod
    def __get_daily_code(dt):
        """
        获取对接标识
        :return:
        """
        return datetime2str(dt, date_format='%Y%m%d000000')

    def merge_search_params(self, m_province_code_list, m_city_code_list):
        stage_list = []
        s_code, e_code = self.__get_daily_code_range()

        match_dict, m_or_list, m_and_list = {}, [], []

        if m_province_code_list:
            m_or_list.append({'province_code': {'$in': m_province_code_list}})
        else:
            m_and_list.append({'province_code': {'$ne': None}})
        if m_city_code_list:
            m_or_list.append({'city_code': {'$in': m_city_code_list}})
        else:
            m_and_list.append({'city_code': {'$ne': None}})

        if m_or_list:
            match_dict['$or'] = m_or_list

        if s_code and e_code:
            m_and_list.append({'daily_code': {'$gte': s_code, '$lte': e_code}})

        if m_and_list:
            match_dict['$and'] = m_and_list

        stage_list.append(MatchStage(match_dict))
        stage_list.append(
            GroupStage({'daily_code': '$daily_code', 'city_code': '$city_code'}, quantity={'$sum': '$quantity'}))
        stage_list.append(SortStage([('_id.daily_code', ASC), ('quantity', DESC)]))
        stage_list.append(LookupStage(AdministrativeDivision, '_id.city_code', 'post_code', 'city_list'))

        return stage_list


def do_generate_cache_key(prefix: str, **kwargs):
    """
    生成缓存key
    :param prefix:
    :param kwargs:
    :return:
    """
    if prefix:
        v_list, v_str = [], ''
        if kwargs:
            for k, v in kwargs.items():
                if v:
                    v_list.append('(%s:%s)' % (k, v))
            if v_list:
                v_str = ''.join(v_list)

        return '%s_%s' % (prefix, md5(v_str))
    return prefix


def format_situation_data(data):
    """
    省级数据 = sum(城市数据)
    :param data:
    :return:
    """

    for province in data:
        province['data'] = sum([city['data'] for city in province['city_list']])

    return data


URL_MAPPING_LIST = [
    url(r'/backoffice/reports/learning/situation/', ReportLearningSituationViewHandler,
        name='backoffice_reports_learning_situation'),
    url(r'/backoffice/reports/learning/situation/cumulative/', ReportLearningSituationCumulativeViewHandler,
        name='backoffice_reports_learning_situation_cumulative'),
    url(r'/backoffice/reports/learning/situation/member/quantity/', ReportLearningSituationMemberQuantityViewHandler,
        name='backoffice_reports_learning_situation_member_quantity'),
    url(r'/backoffice/reports/learning/situation/accuracy/', ReportLearningSituationAccuracyViewHandler,
        name='backoffice_reports_learning_situation_accuracy'),  # 公民科学素质学习效果统计正确率
    url(r'/backoffice/reports/learning/situation/member/active/', ReportLearningSituationMemberActiveViewHandler,
        name='backoffice_reports_learning_situation_member_active'),  # 会员活跃度（按学习日）
    url(r'/backoffice/reports/learning/situation/daily/member/times/',
        ReportLearningSituationDailyMemberTimesViewHandler,
        name='backoffice_reports_learning_situation_daily_member_times'),  # 公民科学素质答题人次趋势(次数)
    url(r'/backoffice/reports/learning/situation/daily/member/quantity/',
        ReportLearningSituationDailyMemberQuantityViewHandler,
        name='backoffice_reports_learning_situation_daily_member_quantity'),  # 公民科学素质答题人次趋势(人数)
    url(r'/backoffice/reports/learning/situation/member/increase/', ReportLearningSituationMemberIncreaseViewHandler,
        name='backoffice_reports_learning_situation_member_increase'),  # 日新增会员排行（Top5）
    url(r'/backoffice/reports/learning/situation/daily/member/quantity/top/',
        ReportLearningSituationDailyMemberQuantityTopViewHandler,
        name='backoffice_reports_learning_situation_daily_member_quantity_top'),  # 日参与会员排行（省、市）
    url(r'/backoffice/reports/learning/tendency/', ReportLearningTendencyViewHandler,
        name='backoffice_reports_learning_tendency'),
    url(r'/backoffice/reports/learning/tendency/subject/quantity/', ReportLearningTendencySubjectQuantityViewHandler,
        name='backoffice_reports_learning_tendency_subject_quantity'),
    url(r'/backoffice/reports/learning/tendency/accuracy/', ReportLearningTendencyAccuracyViewHandler,
        name='backoffice_reports_learning_tendency_accuracy'),  # 公民科学素质答题正确率趋势
    url(r'/backoffice/reports/learning/tendency/dimension/accuracy/',
        ReportLearningTendencyDimensionAccuracyViewHandler,
        name='backoffice_reports_learning_tendency_dimension_accuracy'),  # 答题维度正确率趋势
    url(r'/backoffice/reports/learning/tendency/daily/city/member/top_n/',
        ReportLearningTendencyDailyCityMemberTopNViewHandler,
        name='backoffice_reports_learning_tendency_daily_city_member_top_n'),  # 每日城市新会员Top N
]
