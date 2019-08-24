# !/usr/bin/python
# -*- coding:utf-8 -*-


import datetime
import json

from celery import Celery
from kombu import Queue, Exchange

import settings
from caches.redis_utils import RedisCache
from db.models import Race, AdministrativeDivision, RaceMapping, ReportRacePeopleStatistics, Member, \
    RaceMemberEnterInfoStatistic
from enums import KEY_CACHE_REPORT_ECHARTS_CONDITION
from motorengine import FacadeO, ASC
from motorengine.stages import MatchStage, ProjectStage, GroupStage, SortStage, LookupStage


class TaskCelery(Celery):
    def __init__(self, main=None, loader=None, backend=None, amqp=None, events=None, log=None, control=None,
                 set_as_current=True, tasks=None, broker=None, include=None, changes=None, config_source=None,
                 fixups=None, task_cls=None, autofinalize=True, namespace=None, strict_typing=True, **kwargs):
        super(TaskCelery, self).__init__(
            main=main, loader=loader, backend=backend, amqp=amqp, events=events, log=log, control=control,
            set_as_current=set_as_current, tasks=tasks, broker=broker, include=include, changes=changes,
            config_source=config_source, fixups=fixups, task_cls=task_cls, autofinalize=autofinalize,
            namespace=namespace, strict_typing=strict_typing, **kwargs)

    def task(self, *args, **opts):
        if not opts.get('queue'):
            opts['queue'] = 'default'
        return super(TaskCelery, self).task(*args, **opts)

    def update_config(self, *args, **kwargs):
        """
        更新配置
        :param args:
        :param kwargs:
        :return:
        """
        super(TaskCelery, self).conf.update(*args, **kwargs)

    def get_config(self, name):
        """
        获取配置
        :param name: 配置名
        :return:
        """
        return self.conf.find_value_for_key(name)

    def register_schedule(self, schedule_name: str, func, periodic, *args):
        """
        注册时间循环排班任务
        :return:
        """
        schedule = {
            'task': func,
            'schedule': periodic,
            'args': args
        }
        self.__register_beat_schedule(schedule_name, schedule)

    def __register_beat_schedule(self, schedule_name, schedule: dict):
        if schedule_name and schedule:
            # 所有已注册排版任务
            beat_schedule = self.get_config('beat_schedule')
            if beat_schedule is None:
                beat_schedule = {}

            beat_schedule[schedule_name] = schedule

            self.update_config(beat_schedule=beat_schedule)


def get_task_celery_instance(instance_name, config_module) -> TaskCelery:
    """
    获取一个新的Celery任务实例
    :param instance_name: 实例名称
    :param config_module: 配置对象
    :param use_db: 是否使用DB
    :return:
    """
    if not instance_name:
        raise ValueError('"instance_name" is required.')
    if not isinstance(instance_name, str):
        raise TypeError('"instance_name" only a str.')

    c_instance = TaskCelery(main=instance_name)
    c_instance.config_from_object(config_module)

    return c_instance


DEFAULT_QUEUE = Queue(name='default', exchange=Exchange('celery'), routing_key='celery')


def get_tasks_imports_and_queues():
    """
    获取任务模块&队列
    :return:
    """
    imports, queues = [], [DEFAULT_QUEUE]
    for task_func, queue_name in settings.TASKS_FUNC_MODULE_CFG_LIST:
        if task_func:
            imports.append(task_func)
            if queue_name and not queue_name == 'default':
                queue = Queue(name=queue_name, exchange=Exchange(queue_name), routing_key=queue_name)
                queues.append(queue)
    return imports, queues


def save_cache_condition(task_name, **kwargs):
    """

    :param task_name:
    :param kwargs:
    :return:
    """

    RedisCache.sadd(KEY_CACHE_REPORT_ECHARTS_CONDITION, task_name + '%' + json.dumps(kwargs))


def get_yesterday():
    """
    得到前一天凌晨12点之前的时间
    :return:
    """
    time_match = (datetime.datetime.now() + datetime.timedelta(days=-1)).replace(hour=23, minute=59, second=59,
                                                                                 microsecond=999)
    return time_match


def get_merge_city_data(city_cursor, province_dict, t_province_dict):
    """
    得到整合后的城市数据
    :param city_cursor:
    :param province_dict:
    :param t_province_dict:
    :return:
    """
    while True:
        try:
            city_stat = city_cursor.next()
            city_list = city_stat.city_list
            if not city_list:
                continue
            city: FacadeO = city_list[0]
            if city and city.parent_code:
                p_stat = province_dict.get(city.parent_code)
                if p_stat:
                    if p_stat.get('city_list') is None:
                        p_stat['city_list'] = []
                    p_stat['city_list'].append({
                        'code': city_stat.id,
                        'title': city.title,
                        'data': city_stat.quantity
                    })
                else:
                    province_list = city_stat.province_list
                    if province_list:
                        province: FacadeO = province_list[0]
                        if province:
                            if t_province_dict.get(province.post_code) is None:
                                t_province_dict[province.post_code] = {
                                    'code': province.post_code,
                                    'title': province.title.replace('省', '').replace('市', ''),
                                    'data': 0
                                }
                            #  把省份的个数和城市的个数进行相加整合
                            t_province_dict[province.post_code]['data'] += city_stat.quantity
                            if t_province_dict[province.post_code].get('city_list') is None:
                                t_province_dict[province.post_code]['city_list'] = []
                            t_province_dict[province.post_code]['city_list'].append({
                                'code': city_stat.id,
                                'title': city.title,
                                'data': city_stat.quantity
                            })
        except StopIteration:
            break
    return t_province_dict


def write_sheet_enter_data(book, race_cid, sheet_name, pre_match={}, count_type='$people_num'):
    """
    总共参与人数/人次
    :param book:
    :param sheet_name:
    :param race_cid
    :param pre_match:
    :param count_type:
    :return:
    """

    match = {'race_cid': race_cid}
    if pre_match:
        match.update(pre_match)

    race = Race.sync_get_by_cid(race_cid)
    match.update(get_region_match(race))

    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'district': '$district'}, sum={'$sum': count_type},
                             city={'$first': '$city'})
    daily_list = RaceMemberEnterInfoStatistic.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 2, daily_code)
        daily_map[daily_code] = index + 2

    district_list = RaceMemberEnterInfoStatistic.sync_distinct('district', match)
    district_map = {}
    for index, district in enumerate(district_list):
        sheet.write_string(index + 1, 1, district if district else '其他')
        district_map[district if district else '其他'] = index + 1

    cursor = RaceMemberEnterInfoStatistic.sync_aggregate([MatchStage(match), group_stage])

    county_map = dict()
    v_list = list()
    _max_row = 0
    while True:
        try:
            stat = cursor.next()

            city = stat.city if stat.city else '其他'
            district = stat.id.get('district')
            daily_code = stat.id.get('daily_code')

            _row = district_map.get(district if district else '其他')
            sheet.write_string(_row, 0, city)
            ad_city = AdministrativeDivision.sync_find_one({'title': city})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
            for _c in _county:
                county_map[_c] = city

            sheet.write_number(_row, daily_map.get(daily_code), stat.sum)

            if _row > _max_row:
                _max_row = _row

            v_list.append(stat.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in district_map:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_daily_increase_people(book, race_cid, sheet_name='每日新增参与人数', pre_match={}):
    """
    每日新增人数
    :param book:
    :param sheet_name:
    :param race_cid
    :param pre_match:
    :return:
    """
    race = Race.sync_get_by_cid(race_cid)

    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})

    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})

    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    match = {'race_cid': race_cid, 'record_flag': 1, 'auth_address.province': {'$ne': None}, 'auth_address.city': {"$in": city_name_list},
             'auth_address.district': {"$in": dist_list}}
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMemberEnterInfoStatistic.sync_aggregate(
        [MatchStage(match),
         lookup_stage,
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'auth_address': "$auth_address",
             "member_list": "$member_list"
         }), MatchStage({'member_list': {'$ne': []}}),
         GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'}, sum={'$sum': 1},
                    auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])])

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')

    daily_list = []
    prize_list = []
    county_map = {}

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('district')
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)

                city = data.auth_address.get('city')
                if not city:
                    continue
                sheet.write_string(_current_row, 0, city)
                ad_city = AdministrativeDivision.sync_find_one({'title': city})
                _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
                for _c in _county:
                    county_map[_c] = city

                sheet.write_string(_current_row, 1, title)

            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list) + 1
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 2

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in prize_list:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))


# def write_sheet_daily_pass_people(book, race_cid, sheet_name='每日通关人数', pre_match={}):
#     """
#     每日通关人数
#     :param book:
#     :param race_cid:
#     :param sheet_name:
#     :param pre_match:
#     :return:
#     """
#     race = Race.sync_find_one({'cid': race_cid})
#     _p = AdministrativeDivision.sync_find_one({'code': race.province_code, 'parent_code': None})
#
#     match = {'race_cid': race_cid}
#
#     if pre_match:
#         match.update(pre_match)
#
#     city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
#     dist_list = []
#     for city in city_list:
#         dist_list += AdministrativeDivision.sync_distinct('code', {'parent_code': city})
#
#     match.update({'city_code': {'$in': city_list}, 'district_code': {'$in': dist_list}})
#     last_checkpoint_cid = ''
#     checkpoint_list = RaceGameCheckPoint.sync_find({'race_cid': race_cid, 'record_flag': 1}).to_list(None)
#     if checkpoint_list:
#         last_checkpoint_cid = checkpoint_list[-1].cid
#     check_point_lookup = LookupStage(
#         MemberCheckPointHistory, let={'primary_cid': '$member_cid'},
#         as_list_name='history_list',
#         pipeline=[
#             {'$match': {
#                 '$expr': {
#                     '$and': [
#                         {'$eq': ['$member_cid', '$$primary_cid']},
#                         {'$eq': ['$status', 1]},
#                         {'$eq': ['$check_point_cid', last_checkpoint_cid]}
#                     ]
#                 }
#
#             }
#             },
#         ]
#
#     )
#     match_checkpoint_stage = MatchStage({'history_list': {'$ne': []}})
#     # stats = RaceMapping.sync_aggregate(
#     #     stage_list=[match_stage, check_point_lookup, match_checkpoint_stage])
#     cursor = RaceMapping.sync_aggregate(
#         [MatchStage(match),
#          ProjectStage(**{
#              'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
#              'auth_address': "$auth_address",
#              'member_cid': "$member_cid"
#          }), check_point_lookup, match_checkpoint_stage,
#          GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'}, sum={'$sum': 1},
#                     auth_address={'$first': '$auth_address'}),
#          SortStage([('_id.daily_code', ASC)])])
#     sheet = book.add_worksheet(sheet_name)
#     sheet.write_string(0, 0, '城市')
#     sheet.write_string(0, 1, '区县')
#
#     daily_list = []
#     prize_list = []
#     county_map = {}
#
#     v_list = list()
#     _max_row = 0
#     while True:
#         try:
#             data = cursor.next()
#             _current_row = None
#
#             title = data.id.get('district')
#             if title is None:
#                 title = '未知'
#
#             if title not in prize_list:
#                 prize_list.append(title)
#                 _current_row = len(prize_list)
#
#                 city = data.auth_address.get('city')
#                 if not city:
#                     continue
#                 sheet.write_string(_current_row, 0, city)
#                 ad_city = AdministrativeDivision.sync_find_one({'title': city})
#                 _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
#                 for _c in _county:
#                     county_map[_c] = city
#
#                 sheet.write_string(_current_row, 1, title)
#
#             else:
#                 _current_row = prize_list.index(title) + 1
#
#             daily_code = data.id.get('daily_code')
#             if not daily_code:
#                 daily_code = '未知'
#             if daily_code not in daily_list:
#                 daily_list.append(daily_code)
#                 _current_col = len(daily_list) + 1
#                 sheet.write_string(0, _current_col, daily_code)
#             else:
#                 _current_col = daily_list.index(daily_code) + 2
#
#             sheet.write_number(_current_row, _current_col, data.sum)
#
#             v_list.append(data.sum)
#             if _current_row >= _max_row:
#                 _max_row = _current_row
#
#         except StopIteration:
#             break
#         except Exception as e:
#             raise e
#
#     for k, v in county_map.items():
#         if k not in prize_list:
#             _max_row += 1
#             sheet.write_string(_max_row, 0, v)
#             sheet.write_string(_max_row, 1, k)
#
#     if _max_row:
#         sheet.write_string(_max_row + 1, 0, '总和')
#         sheet.write_number(_max_row + 1, 1, sum(v_list))


def get_region_match(race):
    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})

    return {'city': {'$in': city_name_list}, 'district': {'$in': dist_list}}
