# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import json

from caches.redis_utils import RedisCache
from commons.common_utils import str2datetime
from db.models import RaceMapping, AdministrativeDivision, Race, Member, MemberCheckPointHistory, \
    RaceGameCheckPoint, Company, RedPacketBox, MemberStatisticInfo
from logger import log_utils
from motorengine.stages import MatchStage, ProjectStage, GroupStage
from pymongo.errors import CursorNotFound

logger = log_utils.get_logging('member_stat_schedule', 'member_stat_schedule.log')


def daily_member_statistic(race_cid, daily_code):
    """
    统计每日活动下答过题的会员
    :param race_cid:
    :param daily_code:
    :return:
    """
    start_date = str2datetime(daily_code, '%Y%m%d').replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + datetime.timedelta(days=1)
    check_point_cids, _checkpoint_map = get_checkpoint_cid_list(race_cid)

    # 当日答题记录
    history_match = MatchStage(
        {'created_dt': {'$gte': start_date, '$lt': end_date}, 'check_point_cid': {'$in': check_point_cids}})
    history_group = GroupStage({'member_cid': '$member_cid'}, enter_times={'$sum': 1},
                               results_list={'$push': '$result'})
    history_project = ProjectStage(**{
        'member_cid': '$_id.member_cid',
        'results_list': '$results_list',
        'enter_times': '$enter_times'
    })

    # 红包信息
    member_amount_map = get_red_packet_info(race_cid, start_date, end_date)
    # member_cid: amount

    check_point_history_cursor = MemberCheckPointHistory.sync_aggregate(
        [history_match, history_group, history_project], allowDiskUse=True).batch_size(4)
    member_statistic_list = []
    count = 0
    while True:
        try:
            cursor = check_point_history_cursor.next()
            count += 1
            # 根据member_cid查对应的member信息
            temp_member = Member.sync_get_by_cid(cursor.member_cid)
            if not temp_member:
                logger.info("未找到该会员member_cid:%s" % cursor.member_cid)
                continue
            info = MemberStatisticInfo()
            info.daily_code = daily_code
            info.race_cid = race_cid
            # 会员信息
            info.member_cid = cursor.member_cid
            info.nick_name = temp_member.nick_name
            info.open_id = temp_member.open_id
            info.mobile = temp_member.mobile
            info.first_time_login = temp_member.created_dt
            info.enter_times = cursor.enter_times
            # 答题数量、正确数
            for results in cursor.results_list:
                info.answer_times += len(results)
                info.true_answer_times += len([result for result in results if result.get('true_answer')])

            # race_mapping相关信息,地理位置
            has_race_mapping = get_race_mapping_info(info)
            if not has_race_mapping:
                logger.info("normal未找到对应race_mapping,race_cid:%s,member_cid:%s" % (info.race_cid, info.member_cid))
                continue
            # 是否为当日新用户
            is_new_user(info)
            # 最后一关
            is_final_pass(info)

            # 红包信息
            try:
                value = member_amount_map.pop(info.member_cid)
            except KeyError:
                value = None

            if not value:
                value = {'grant_count': 0, 'grant_amount': 0, 'draw_count': 0, 'draw_amount': 0}

            info.grant_red_packet_amount = value.get('grant_amount')
            info.grant_red_packet_count = value.get('grant_count')
            info.draw_red_packet_amount = value.get('draw_amount')
            info.draw_red_packet_count = value.get('draw_count')

            # 保存记录
            member_statistic_list.append(info)
            logger.info("Success: member_cid:%s is_final_Pass:%s is_new:%s" % (
                info.member_cid, info.is_final_passed, info.is_new_user))
            # print("Success: member_cid:%s is_final_Pass:%s is_new:%s" % (info.member_cid, info.is_final_passed,info.is_new_user))
            if len(member_statistic_list) % 500 == 0:
                MemberStatisticInfo.sync_insert_many(member_statistic_list)
                member_statistic_list = []
        except StopIteration:
            break
        except CursorNotFound:
            check_point_history_cursor = MemberCheckPointHistory.sync_aggregate(
                [history_match, history_group, history_project]).skip(count).batch_size(4)
        except Exception as e:
            logger.error(e)
            logger.info("Fail: daily_code:%s,race_cid: %s" % (daily_code, race_cid))
            member_statistic_list = []

    member_statistic_list += insert_from_member_amount_map(member_amount_map, daily_code, race_cid)
    if len(member_statistic_list) > 0:
        MemberStatisticInfo.sync_insert_many(member_statistic_list)


def insert_from_member_amount_map(member_amount_map: dict, daily_code, race_cid):
    """
    处理今日未答题，但是领取红包的会员
    :param member_amount_map:
    :param daily_code:
    :return:
    """
    if not member_amount_map:
        return []

    ret_list = []
    for member_cid, value in member_amount_map.items():
        temp_member = Member.sync_get_by_cid(member_cid)
        if not temp_member:
            logger.info("RedPacket,未找到该会员member_cid:%s" % member_cid)
            continue
        info = MemberStatisticInfo()
        info.daily_code = daily_code
        info.race_cid = race_cid
        # 会员信息
        info.member_cid = member_cid
        info.nick_name = temp_member.nick_name
        info.open_id = temp_member.open_id
        info.mobile = temp_member.mobile
        info.first_time_login = temp_member.created_dt

        # race_mapping相关信息,地理位置
        has_race_mapping = get_race_mapping_info(info)
        if not has_race_mapping:
            logger.info("RedPacket未找到对应race_mapping,race_cid:%s,member_cid:%s" % (info.race_cid, info.member_cid))
            continue

        # 是否为当日新用户
        is_new_user(info)
        # 最后一关
        is_final_pass(info)

        info.grant_red_packet_amount = value.get('grant_amount')
        info.grant_red_packet_count = value.get('grant_count')
        info.draw_red_packet_amount = value.get('draw_amount')
        info.draw_red_packet_count = value.get('draw_count')
        ret_list.append(info)

    return ret_list


def deal_member_without_history(race_cid, daily_code):
    """
    处理今日报名活动但未答题的会员
    :param race_cid:
    :param daily_code:
    :return:
    """
    city_name_list, district_name_list = get_address(race_cid)
    checkpoint_cid, _checkpoint_map = get_checkpoint_cid_list(race_cid)
    start_date = str2datetime(daily_code, '%Y%m%d').replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + datetime.timedelta(days=1)

    member_cid_with_history = MemberCheckPointHistory.sync_distinct("member_cid",
                                                                    {'check_point_cid': {'$in': checkpoint_cid},
                                                                     'created_dt': {'$gte': start_date,
                                                                                    '$lt': end_date}})
    race_member_match = MatchStage({"race_cid": race_cid, 'member_cid': {'$nin': member_cid_with_history},
                                    'auth_address.city': {"$in": city_name_list},
                                    'auth_address.district': {"$in": district_name_list},
                                    'created_dt': {'$gte': start_date, '$lt': end_date}})
    member_group = GroupStage({'member_cid': '$member_cid'}, auth_address={'$first': '$auth_address'},
                              company_cid={'$first': '$company_cid'},
                              mobile={'$first': '$mobile'},
                              created_dt={'$first': '$created_dt'})
    member_project = ProjectStage(**{
        'cid': '$cid',
        'member_cid': '$_id.member_cid',
        'auth_address': '$auth_address',
        'mobile': '$mobile',
        'created_dt': '$created_dt',
        'company_cid': '$company_cid'
    })
    member_without_history = RaceMapping.sync_aggregate(
        [race_member_match, member_group, member_project]).batch_size(4)

    member_amount_map = get_red_packet_info(race_cid, start_date, end_date)

    red_member_cid_list = member_amount_map.keys()
    member_no_history_list = []
    count = 0
    while True:
        try:
            stat = member_without_history.next()
            count += 1
            if stat.member_cid in red_member_cid_list:
                continue
            # 根据member_cid查对应的member信息
            temp_member = Member.sync_get_by_cid(stat.member_cid)
            if not temp_member:
                logger.info("no history:未找到该会员member_cid:%s" % stat.member_cid)
                continue
            info_special = MemberStatisticInfo()
            info_special.is_special_user = 1
            info_special.race_cid = race_cid
            info_special.member_cid = stat.member_cid
            info_special.daily_code = format(stat.created_dt, '%Y%m%d')
            info_special.nick_name = temp_member.nick_name
            info_special.open_id = temp_member.open_id
            if stat.mobile:
                info_special.mobile = stat.mobile
            else:
                info_special.mobile = temp_member.mobile
            info_special.first_time_login = temp_member.created_dt
            info_special.enter_times = 1
            info_special.answer_times = 0
            info_special.true_answer_times = 0
            info_special.is_final_passed = 0
            info_special.is_new_user = 1
            info_special.grant_red_packet_amount = 0.0
            info_special.grant_red_packet_count = 0
            info_special.draw_red_packet_count = 0
            info_special.draw_red_packet_amount = 0.0

            info_special.province = stat.auth_address.get('province')
            info_special.city = stat.auth_address.get('city')
            info_special.district = stat.auth_address.get('district')
            info_special.town = stat.auth_address.get('town')
            info_special.check_point_cid = stat.race_check_point_cid
            if stat.race_check_point_cid:
                info_special.check_point_index = _checkpoint_map[stat.race_check_point_cid]
            else:
                info_special.check_point_index = 1
            if stat.company_cid:
                company = Company.sync_get_by_cid(stat.company_cid)
                info_special.company_cid = company.cid
                info_special.company_name = company.title

            member_no_history_list.append(info_special)
            # logger.info("Success without history: member_cid:%s is_final_Pass:%s" % (info_special.member_cid,info_special.is_final_passed))
            if len(member_no_history_list) % 500 == 0:
                MemberStatisticInfo.sync_insert_many(member_no_history_list)
                member_no_history_list = []
        except StopIteration:
            break
        except CursorNotFound:
            member_without_history = RaceMapping.sync_aggregate(
                [race_member_match, member_group, member_project]).skip(count).batch_size(4)
        except Exception as e:
            logger.info("Fail: without history daily_code:%s,member_cid:%s,race_cid: %s" % (
                info_special.daily_code, info_special.member_cid, race_cid))
    if len(member_no_history_list) > 0:
        MemberStatisticInfo.sync_insert_many(member_no_history_list)


def get_race_mapping_info(info: MemberStatisticInfo):
    """
    获取行政区域信息、公司单位、当前关卡
    :param info:
    :return:
    """
    race_cid = info.race_cid
    member_cid = info.member_cid
    city_name_list, district_name_list = get_address(race_cid)
    check_point_cids, _checkpoint_map = get_checkpoint_cid_list(race_cid)
    race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': member_cid,
                                              'auth_address.province': {'$ne': None},
                                              'auth_address.city': {"$in": city_name_list},
                                              'auth_address.district': {"$in": district_name_list}})
    if race_mapping:
        info.province = race_mapping.auth_address.get('province')
        info.city = race_mapping.auth_address.get('city')
        info.district = race_mapping.auth_address.get('district')
        info.town = race_mapping.auth_address.get('town')
        info.mobile = race_mapping.mobile
        info.check_point_cid = race_mapping.race_check_point_cid
        if race_mapping.race_check_point_cid:
            info.check_point_index = _checkpoint_map[race_mapping.race_check_point_cid]
        else:
            info.check_point_index = 1

        # 单位信息
        if race_mapping.company_cid:
            company = Company.sync_get_by_cid(race_mapping.company_cid)
            info.company_cid = company.cid
            info.company_name = company.title
        return True
    else:
        return False


def is_final_pass(info: MemberStatisticInfo):
    """
    判断该用户是否通关
    :param info:
    :return:
    """
    race_cid = info.race_cid
    member_cid = info.member_cid

    last_check_point_cid = get_last_check_point_cid(race_cid)
    # 当前关卡不是最后一关，则未通关
    if info.check_point_cid != last_check_point_cid:
        info.is_final_passed = 0
    else:
        # 如果答题历史表中有最后一关答题记录且答题成功，则通关
        record = MemberCheckPointHistory.sync_find_one(
            {'member_cid': member_cid, 'check_point_cid': last_check_point_cid,
             'status': 1})
        if record:
            info.is_final_passed = 1
        else:
            info.is_final_passed = 0


def is_new_user(info: MemberStatisticInfo):
    """
    判断是否为当日新用户
    :param info:
    :return:
    """
    race_cid = info.race_cid
    member_cid = info.member_cid
    current_date = str2datetime(info.daily_code, '%Y%m%d').replace(hour=0, minute=0, second=0, microsecond=0)
    checkpoint_cid_list, _checkpoint_map = get_checkpoint_cid_list(race_cid)
    has_history = MemberCheckPointHistory.sync_find_one(
        {'member_cid': member_cid, 'check_point_cid': {'$in': checkpoint_cid_list},
         'created_dt': {'$lt': current_date}})
    if has_history:
        race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': member_cid})
        # 处理异常情况:在报名活动之前就有答题记录,报名时间是否为当天，如果是，则为新用户
        if format(race_mapping.created_dt, "%Y%m%d") == info.daily_code:
            info.is_new_user = 1
        else:
            pre_info = MemberStatisticInfo.sync_find_one(
                {'race_cid': race_cid, 'member_cid': member_cid, 'daily_code': {'$lt': info.daily_code},
                 'is_new_user': 1})
            if pre_info:
                info.is_new_user = 0
            else:
                info.is_new_user = 1
    else:
        # 之前报名活动，但当日未答题，之后答题的情况,报名时间是否为当天，如果是，则为新用户
        race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': member_cid})
        if format(race_mapping.created_dt, "%Y%m%d") == info.daily_code:
            info.is_new_user = 1
        else:
            pre_info = MemberStatisticInfo.sync_find_one(
                {'race_cid': race_cid, 'member_cid': member_cid, 'daily_code': {'$lt': info.daily_code}, 'is_new_user': 1})
            if pre_info:
                info.is_new_user = 0
            else:
                info.is_new_user = 1


def get_red_packet_info(race_cid, start_date, end_date):
    """
    统计当日该会员参加活动时，红包领取数量、领取金额、发放数量
    :param race_cid:
    :param start_date:
    :param end_date:
    :return:
    """
    cursor = RedPacketBox.sync_aggregate([
        MatchStage(
            {'draw_dt': {"$gte": start_date, "$lt": end_date}, 'race_cid': race_cid, 'award_cid': {'$ne': None}}),
        GroupStage({'member_cid': '$member_cid', 'draw_status': '$draw_status'}, amount={'$sum': '$award_amount'},
                   sum={"$sum": 1})
    ])

    ret = {}
    while True:
        try:
            data = cursor.next()

            _member = data.id.get('member_cid')
            _status = data.id.get('draw_status')
            _value = ret.get(_member)
            if not _value:
                _value = {'grant_count': 0, 'grant_amount': 0, 'draw_count': 0, 'draw_amount': 0}

            _value['grant_count'] += data.sum
            _value['grant_amount'] += data.amount
            if _status == 0:
                _value['draw_count'] += data.sum
                _value['draw_amount'] += data.amount
            ret[_member] = _value
        except StopIteration:
            break

    return ret


def get_checkpoint_cid_list(race_cid):
    """
    获取活动的所有关卡的cid，并缓存
    :param race_cid:
    :return:
    """
    key = '%s_CHECK_POINT_CID' % race_cid
    map_key = '%s_CHECK_POINT_MAP' % race_cid
    check_point_cid_list_str = RedisCache.get(key)
    check_point_map_str = RedisCache.get(map_key)
    if check_point_map_str and check_point_cid_list_str:
        check_point_cid_list = check_point_cid_list_str.split(',')
        checkpoint_map = json.loads(check_point_map_str)
    else:
        check_point_list = RaceGameCheckPoint.sync_find({'race_cid': race_cid}).sort(
            'index').to_list(None)
        check_point_cid_list = []
        checkpoint_map = dict()
        for check_point in check_point_list:
            check_point_cid_list.append(check_point.cid)
            checkpoint_map[check_point.cid] = check_point.index
        # 缓存所有关卡的cid
        RedisCache.set(key, ",".join(check_point_cid_list), 6 * 60 * 60)
        RedisCache.set(map_key, json.dumps(checkpoint_map), 6 * 60 * 60)
    return check_point_cid_list, checkpoint_map


def get_last_check_point_cid(race_cid):
    """
    获取最后一关的cid,并缓存
    :param race_cid:
    :return:
    """
    key = '%s_LAST_CHECK_POINT_CID' % race_cid
    last_check_point_cid = RedisCache.get(key)
    if not last_check_point_cid:
        check_point_cid_list, _checkpoint_map = get_checkpoint_cid_list(race_cid)
        # 缓存最后一关的cid,以及所有关卡cid
        last_check_point_cid = check_point_cid_list[-1]
        RedisCache.set(key, last_check_point_cid, 6 * 60 * 60)
    return last_check_point_cid


def get_address(race_cid):
    """
    获取活动的城市列表、区域列表,并缓存
    :param race_cid:
    :return:
    """
    city_list_str_key = '%s_CITY_LIST_STR' % race_cid
    district_list_str_key = '%s_DISTRICT_LIST_STR' % race_cid
    city_name_list_str = RedisCache.get(city_list_str_key)
    district_name_list_str = RedisCache.get(district_list_str_key)
    if not city_name_list_str or not district_name_list_str:
        # race_province_code,race_city_code缓存,若city_code不为空，则为市级活动
        pro_code_key = '%s_province_code' % race_cid
        city_code_key = '%s_city_code' % race_cid
        province_code = RedisCache.get(pro_code_key)
        city_code = RedisCache.get(city_code_key)
        if not province_code or not city_code:
            race = Race.sync_get_by_cid(race_cid)
            RedisCache.set(pro_code_key, race.province_code, 12 * 60 * 60)
            RedisCache.set(city_code_key, race.city_code, 12 * 60 * 60)
        if city_code:
            city_code_list = AdministrativeDivision.sync_distinct('code', {'code': city_code})
            city_name_list = AdministrativeDivision.sync_distinct('title', {'code': city_code})
        else:
            city_code_list = AdministrativeDivision.sync_distinct('code', {'parent_code': province_code})
            city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': province_code})
        district_name_list = AdministrativeDivision.sync_distinct('title',
                                                                  {'parent_code': {'$in': city_code_list}})
        RedisCache.set(','.join(city_name_list), 12 * 60 * 60)
        RedisCache.set(','.join(district_name_list), 12 * 60 * 60)
    else:
        city_name_list = city_name_list_str.split(',')
        district_name_list = district_name_list_str.split(',')
    return city_name_list, district_name_list


def get_date_range(start_date):
    """
    获取活动开始到至今的时间段
    :param start_date:
    :return:
    """
    date_list = []
    end_date = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    while start_date < end_date:
        date_str = start_date.strftime("%Y%m%d")
        date_list.append(date_str)
        start_date += datetime.timedelta(days=1)
    return date_list


def clear(race_cid, daily_code):
    """
    清空一天数据
    :param race_cid:
    :param daily_code:
    :return:
    """
    MemberStatisticInfo.sync_delete_many({"race_cid": race_cid, 'daily_code': daily_code})


def task_many_day(race_cid, date_list):
    """
    处理从开始日期到现在的数据
    :param race_cid:
    :param date_list:
    :return:
    """
    key = '%s_CHECK_POINT_CID' % race_cid
    map_key = '%s_CHECK_POINT_MAP' % race_cid
    last_key = '%s_LAST_CHECK_POINT_CID' % race_cid
    RedisCache.delete(key)
    RedisCache.delete(map_key)
    RedisCache.delete(last_key)
    for daily_code in date_list:
        # print('开始处理', daily_code)
        clear(race_cid, daily_code)
        daily_member_statistic(race_cid, daily_code)
        deal_member_without_history(race_cid, daily_code)


def clear_redis_cache(race_cid):
    key = '%s_CHECK_POINT_CID' % race_cid
    map_key = '%s_CHECK_POINT_MAP' % race_cid
    last_key = '%s_LAST_CHECK_POINT_CID' % race_cid
    RedisCache.delete(key)
    RedisCache.delete(map_key)
    RedisCache.delete(last_key)


def task_one_day(race_cid, daily_code=None):
    """
    处理一天的数据
    :param race_cid:
    :param daily_code:
    :return:
    """
    if not daily_code:
        now = datetime.datetime.now()
        daily_code = format(now, '%Y%m%d')
    clear(race_cid, daily_code)
    daily_member_statistic(race_cid, daily_code)
    deal_member_without_history(race_cid, daily_code)


def start(daily_code_list=None, one_daily_code=None):
    """
    统计会员信息，主方法
    :param daily_code_list:
    :param one_daily_code:
    :return:
    """
    race_cid_list = Race.sync_distinct('cid', {'status': 1})
    for race_cid in race_cid_list:
        logger.info('START RACE : %s' % race_cid)
        if daily_code_list:
            task_many_day(race_cid, daily_code_list)
        else:
            task_one_day(race_cid, one_daily_code)
        logger.info('END RACE : %s' % race_cid)


def start2(race_cid, daily_code_list=None):
    """
    统计会员信息，主方法
    :param daily_code_list:
    :param one_daily_code:
    :return:
    """
    # print('START RACE : %s' % race_cid)
    task_many_day(race_cid, daily_code_list)
    # print('END RACE : %s' % race_cid)


if __name__ == '__main__':
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D 扬州 DF1EDC30F120AEE93351A005DC97B5C1
    _race_cid = 'CA755167DEA9AA89650D11C10FAA5413'
    daily_codes_list = ['20190628', '20190629', '20190630', '20190701', '20190702', '20190703', '20190704', '20190705',
                        '20190706', '20190707']
    start2(_race_cid, daily_codes_list)
    # task_one_day(_race_cid, '20190628')
