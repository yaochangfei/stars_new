import datetime

import msgpack

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str
from db import CITY_RACE_CID
from db.models import Race, AdministrativeDivision, Member, \
    RaceMemberEnterInfoStatistic
from motorengine import DESC, log_utils
from motorengine.stages import MatchStage, GroupStage, ProjectStage, SortStage, LookupStage

logger_cache = log_utils.get_logging('race_cache', 'race_cache.log')


def get_city_and_district(race_cid):
    """
    得到安徽下面的所有市和区
    :param race_cid:
    :return:
    """
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    race = Race.sync_get_by_cid(race_cid)

    city_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})

    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})

    dist_list = []
    for city in city_list:
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city})
    return city_name_list, dist_list, lookup_stage


async def stat_data(cursor):
    """

    :param cursor:
    :param race_cid
    :param type
    :param category
    :return:
    """
    data = {}
    while await cursor.fetch_next:
        stat = cursor.next_object()
        data[stat.id] = stat.sum
    return data


async def do_stat_member_times(race_cid: str, time_match: MatchStage, group_id='district', name_match=MatchStage({}),
                               district_title="", name="", time_num="", is_integrate=""):
    """
    统计参赛人次

    :param race_cid:
    :param time_match:
    :param group_id:
    :param name_match
    :param district_title
    :param name
    :param time_num
    :param is_integrate
    :return:
    """
    if not race_cid:
        return

    cache_key = get_cache_key(race_cid,
                              'member_times_{district}_{name}_{time_num}_{district_title}_{is_integrate}'.format(
                                  district=group_id,
                                  name=name,
                                  time_num=time_num,
                                  district_title=district_title,
                                  is_integrate=is_integrate))
    member_times_data = RedisCache.get(cache_key)
    data_cache = ''
    if member_times_data:
        data_cache = msgpack.unpackb(member_times_data, raw=False)
    if not member_times_data or not data_cache:
        # race = await Race.get_by_cid(race_cid)
        all_match = {'race_cid': race_cid}
        # 安徽特殊处理，需整合六安数据(弃用)
        if is_integrate:
            all_match = {'race_cid': {'$in': [race_cid, CITY_RACE_CID]}}
        district_match = MatchStage({})
        if district_title:
            district_match = MatchStage({'district': district_title})
            all_match['town'] = {'$ne': None}

        cursor = RaceMemberEnterInfoStatistic.aggregate([
            MatchStage(all_match),
            district_match,
            time_match,
            name_match,
            GroupStage(group_id, sum={'$sum': '$enter_times'}),
            SortStage([('sum', DESC)])
        ])
        times_data = await stat_data(cursor)
        logger_cache.info('cache_key: %s' % cache_key)
        RedisCache.set(cache_key, msgpack.packb(times_data), 23 * 60 * 60)
        return times_data
    return msgpack.unpackb(member_times_data, raw=False)


async def do_stat_member_count(race_cid: str, time_match: MatchStage, group_id, name_match=MatchStage({}),
                               district_title="", district_match=MatchStage({}), name="", time_num="", is_integrate=""):
    """
    统计参赛人数

    :param race_cid:
    :param time_match:
    :param group_id:
    :param name_match
    :param district_title
    :param is_integrate
    :param district_match
    :param name
    :param time_num
    :return:
    """

    if not race_cid:
        return
    cache_key = get_cache_key(race_cid,
                              'member_count_{district}_{name}_{time_num}_{district_title}_{is_integrate}'.format(
                                  district=group_id,
                                  name=name,
                                  time_num=time_num,
                                  district_title=district_title, is_integrate=is_integrate))
    member_count_data = RedisCache.get(cache_key)
    data_cache = ''
    if member_count_data:
        data_cache = msgpack.unpackb(member_count_data, raw=False)
    if not member_count_data or not data_cache:
        #  城镇排行榜是具体某个区下面的
        if district_title:
            district_match = MatchStage({'district': district_title, 'town': {'$ne': None}})
        # 安徽特殊处理，需整合六安数据(弃用)
        # race = await Race.get_by_cid(race_cid)
        all_match = {'race_cid': race_cid}
        if is_integrate:
            all_match = {'race_cid': {'$in': [race_cid, CITY_RACE_CID]}}
        cursor = RaceMemberEnterInfoStatistic.aggregate([
            MatchStage(all_match),
            district_match,
            time_match,
            name_match,
            GroupStage(group_id, sum={'$sum': '$increase_enter_count'})
        ])
        count_data = await stat_data(cursor)
        logger_cache.info('cache_key: %s' % cache_key)
        RedisCache.set(cache_key, msgpack.packb(count_data), 23 * 60 * 60)
        return count_data
    return msgpack.unpackb(member_count_data, raw=False)


async def do_stat_member_accuracy(race_cid: str, time_match: MatchStage, group_id, district_title="", time_num=""):
    """
    统计参赛正确率

    :param race_cid:
    :param time_match:
    :param group_id:
    :param district_title
    :return:
    """

    if not race_cid:
        return
    cache_key = get_cache_key(race_cid,
                              'member_accuracy_{district}_{time_num}_{district_title}'.format(district=group_id,
                                                                                              time_num=time_num,
                                                                                              district_title=district_title))
    member_accuracy_data = RedisCache.get(cache_key)
    if member_accuracy_data:
        data_cache = msgpack.unpackb(member_accuracy_data, raw=False)
    if not member_accuracy_data or not data_cache:
        district_match = MatchStage({})
        if district_title:
            district_match = MatchStage({'district': district_title})
        # 安徽特殊处理，需整合六安数据(弃用)
        # race = await Race.get_by_cid(race_cid)
        all_match = {'race_cid': race_cid}
        # if race.province_code == '340000':
        #     all_match = {'race_cid': {'$in': [race_cid, CITY_RACE_CID]}}
        cursor = RaceMemberEnterInfoStatistic.aggregate([
            MatchStage(all_match),
            time_match,
            district_match,
            GroupStage(group_id, total_correct={'$sum': "$true_answer_times"},
                       total_count={'$sum': '$answer_times'}),
            ProjectStage(**{
                'city': "$city",
                'sum': {
                    '$cond': {
                        'if': {'$eq': ['$total_count', 0]},
                        'then': 0,
                        'else': {
                            '$divide': ['$total_correct', '$total_count']
                        }
                    }
                }
            })
        ])
        accuracy_data = await stat_data(cursor)
        logger_cache.info('cache_key: %s' % cache_key)
        RedisCache.set(cache_key, msgpack.packb(accuracy_data), 23 * 60 * 60)
        return accuracy_data
    return msgpack.unpackb(member_accuracy_data, raw=False)


async def get_drill_district_data(data_dict, name):
    """
    获得下钻到区的数据
    :param data_dict:
    :param name
    :return:
    """
    data_list = []
    total = 0
    for title, data in zip(data_dict.keys(), data_dict.values()):
        temple_dict = {}
        temple_dict['title'] = title
        temple_dict['data'] = data
        total += data
        data_list.append(temple_dict)
    data_list.sort(key=lambda x: -x.get('data'))
    return data_list, total


def generate_cache_key(category):
    """
    生成当日缓存key
    :param category:
    :return:
    """
    today = datetime2str(datetime.datetime.now(), date_format='%Y%m%d')
    return "{today}-{category}".format(today=today, category=category)


def get_cache_key(race_cid, category):
    """
    生成当日缓存key
    :param category:
    :return:
    """
    today = datetime2str(datetime.datetime.now(), date_format='%Y%m%d')
    return "{race_cid}-{today}-{category}".format(race_cid=race_cid, today=today, category=category)


async def do_rank_statistic(race_cid: str, time_match: MatchStage, group_id='district', name_match=MatchStage({}),
                            district_title="", name="", time_num=""):
    """
    统计活动信息

    :param race_cid:
    :param time_match:
    :param group_id:
    :param name_match
    :param district_title
    :param
    :return:
    """
    if not race_cid:
        return

    cache_key = generate_cache_key(
        'member_times_{district}_{name}_{time_num}_{district_title}'.format(district=group_id, name=name,
                                                                            time_num=time_num,
                                                                            district_title=district_title))
    member_times_data = RedisCache.hget(race_cid, cache_key)
    if not member_times_data:
        race = await Race.get_by_cid(race_cid)

        city_list = await AdministrativeDivision.distinct('code', {'parent_code': race.province_code})
        city_name_list = await AdministrativeDivision.distinct('title', {'parent_code': race.province_code})
        dist_list = []
        for city in city_list:
            dist_list += await AdministrativeDivision.distinct('title', {'parent_code': city})
        district_match = MatchStage({})
        all_match = {'race_cid': race_cid, 'province': {'$ne': None},
                     'district': {'$in': dist_list}, 'city': {'$in': city_name_list}}

        if district_title:
            district_match = MatchStage({'district': district_title})
            all_match['city'] = {'$in': city_name_list}
            all_match['town'] = {'$ne': None}
        cursor = RaceMemberEnterInfoStatistic.aggregate([
            MatchStage(all_match),
            district_match,
            time_match,
            name_match,
            GroupStage(group_id, enter_times_sum={'$sum': '$enter_times'}, people_sum={'$sum': '$increase_enter_count'},
                       true_answer_times_sum={'$sum': '$true_answer_times'},
                       answer_times_sum={'$sum': '$answer_times'}),
            SortStage([('enter_times_sum', DESC)])
        ])
        times_data = await stat_data(cursor)
        logger_cache.info('cache_key: %s' % cache_key)
        RedisCache.hset(race_cid, cache_key, msgpack.packb(times_data))
        return times_data
    return msgpack.unpackb(member_times_data, raw=False)


async def stat_data2(cursor):
    """

    :param cursor:
    :param race_cid
    :param type
    :param category
    :return:
    """
    data = {}
    while await cursor.fetch_next:
        stat = cursor.next_object()
        _value = {'enter_times_sum': stat.enter_times_sum, 'people_sum': stat.people_sum}
        if stat.answer_times_sum:
            _value['correct_rate'] = stat.true_answer_times_sum / stat.answer_times_sum
        data[stat.id] = _value
    return data


def get_special_cache_key(race_cid, category):
    """
    生成安徽报告缓存key
    :param race_cid
    :param category:
    :return:
    """
    today = datetime2str(datetime.datetime.now(), date_format='%Y%m%d')
    return "{race_cid}_{today}_{category}".format(race_cid=race_cid, today=today, category=category)