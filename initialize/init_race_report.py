"""
初始化活动每日参与人数数据
"""

import pdb

from caches.redis_utils import RedisCache
from commons.common_utils import datetime2str, md5
from db import STATUS_RESULT_CHECK_POINT_WIN
from db.models import RaceGameCheckPoint, MemberCheckPointHistory, ReportRacePeopleStatistics, Race, \
    AdministrativeDivision, Member, RaceMapping
from motorengine import ASC
from pymongo import ReadPreference
from pymongo.errors import CursorNotFound


def get_all_race_checkpoint_map():
    """
    获取所有活动
    :return:
    """
    _mp = {}
    cursor = RaceGameCheckPoint.sync_find()
    while True:
        try:
            cp = cursor.next()
            _mp[cp.cid] = cp.race_cid
        except StopIteration:
            break

    return _mp


def get_all_last_checkpoint():
    """
    获取每个活动的最后一关
    :return:
    """

    _lp = {}
    race_list = Race.sync_find().to_list(None)
    for race in race_list:
        checkpoint = RaceGameCheckPoint.sync_find({'race_cid': race.cid}).sort([('index', ASC)]).to_list(None)
        if checkpoint:
            _lp[race.cid] = checkpoint[-1].cid

    return _lp


def __get_daily_code(dt):
    """
    获取对接标识
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d')


def init_race_stat_data():
    """
    初始该活动数据
    :return:
    """

    cp_map = get_all_race_checkpoint_map()
    last_map = get_all_last_checkpoint()

    cursor = MemberCheckPointHistory.sync_find({'check_point_cid': {'$in': list(cp_map.keys())}},
                                               read_preference=ReadPreference.PRIMARY).sort('created_dt').limit(600000)
    cache_key = 'race_report_script'
    RedisCache.delete(cache_key)

    index = 1
    while True:
        try:
            his = cursor.next()

            mapping = RaceMapping.sync_find_one(
                {'member_cid': his.member_cid, 'race_cid': cp_map.get(his.check_point_cid)})
            member = Member.sync_find_one({'cid': his.member_cid})

            auth_address = mapping.auth_address if mapping else None

            # if not auth_address:
            #     auth_address = member.auth_address
            #
            if not auth_address:
                continue

            race_cid = cp_map[his.check_point_cid]
            daily_code = __get_daily_code(his.created_dt)
            param = {'race_cid': race_cid, 'province': auth_address.get('province'),
                     'city': auth_address.get('city'), 'district': auth_address.get('district'),
                     'sex': member.sex, 'education': member.education, 'category': member.category,
                     'daily_code': daily_code}
            stat = ReportRacePeopleStatistics.sync_find_one(param, read_preference=ReadPreference.PRIMARY)

            if not stat:
                stat = ReportRacePeopleStatistics(**param)
                stat.created_dt = his.created_dt

            stat.total_num += 1
            # 初次通关
            if his.check_point_cid == last_map[
                race_cid] and his.status == STATUS_RESULT_CHECK_POINT_WIN and RedisCache.hget(cache_key,
                                                                                              member.cid) is None:
                stat.pass_num += 1
                RedisCache.hset(cache_key, member.cid, 1)

            # 当日人数
            day_member_string = md5(daily_code + member.cid)
            if RedisCache.hget(cache_key, day_member_string) is None:
                RedisCache.hset(cache_key, day_member_string, 1)
                stat.people_num += 1

            # # 当日新增人数
            # old_his = MemberCheckPointHistory.sync_find_one({'member_cid': member.cid, 'created_dt': {
            #     '$lt': his.updated_dt.replace(hour=0, minute=0, second=0, microsecond=0)}})
            # if not old_his:
            #     stat.incre_people += 1

            stat.updated_dt = his.updated_dt
            stat.sync_save()
            print('has exec %s' % index)
            index += 1
        except StopIteration:
            break
        except CursorNotFound:
            cursor = MemberCheckPointHistory.sync_find({'check_point_cid': {'$in': list(cp_map.keys())}},
                                                       read_preference=ReadPreference.PRIMARY). \
                sort('created_dt').skip(index).limit(600000 - index)

    RedisCache.delete(cache_key)


def wash_data():
    """
    清洗统计数据
    :return:
    """

    race_map = {}
    prov_map = {}

    cursor = ReportRacePeopleStatistics.sync_find()

    while True:
        try:
            stat = cursor.next()
            if not (stat.province and stat.city and stat.district):
                print('delete')
                stat.sync_delete()
                continue

            if race_map.get(stat.race_cid):
                race = race_map.get(stat.race_cid)
            else:
                race = Race.sync_find_one({'cid': stat.race_cid})
                race_map[stat.race_cid] = race
            prov = prov_map.get(stat.province)
            if not prov:
                prov = AdministrativeDivision.sync_find_one({'title': {'$regex': stat.province}, 'parent_code': None})
                prov_map[stat.province] = prov

            if prov.code != race.province_code:
                print('xxxxx')
                stat.sync_delete()
        except StopIteration:
            break
        except Exception as e:
            pdb.set_trace()

    cursor = RaceMapping.sync_find()
    while True:
        try:
            _p = cursor.next()
            if not _p.auth_address or not _p.auth_address.get('district'):
                member = Member.sync_find_one({'cid': _p.member_cid})
                if not member or not member.auth_address or not member.auth_address.get('district'):
                    _p.sync_delete()
                    continue

                _p.auth_address = member.auth_address
                _p.sync_save()
                print('update mapping')

            if race_map.get(_p.race_cid):
                race = race_map.get(_p.race_cid)
            else:
                race = Race.sync_find_one({'cid': _p.race_cid})
                race_map[_p.race_cid] = race

            province = _p.auth_address.get('province')
            if province:
                prov = prov_map.get(province)
                if not prov:
                    prov = AdministrativeDivision.sync_find_one({'title': {'$regex': province}, 'parent_code': None})
                    prov_map[province] = prov.code

                if prov.code != race.province_code:
                    print(' mapping delete ')
                    _p.sync_delete()

        except StopIteration:
            break
        except Exception as e:
            print(e)
            raise e


if __name__ == '__main__':
    init_race_stat_data()
