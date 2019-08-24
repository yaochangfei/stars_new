# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import pickle

import msgpack
from pymongo import UpdateOne

from caches.redis_utils import RedisCache
from db import SOURCE_MEMBER_INTEGRAL_LIST, SOURCE_MEMBER_INTEGRAL_DICT, SOURCE_MEMBER_DIAMOND_LIST, \
    SOURCE_MEMBER_DIAMOND_DICT
from db.models import VehicleAttribute, MemberIntegralDetail, MemberIntegralSource, Member, MemberDiamondDetail, \
    GameDiamondReward, SubjectDimension, SubjectChoiceRules, AdministrativeDivision
from enums import KEY_CODE_VEHICLE_ATTRIBUTE, KEY_ANSWER_LIMIT, KEY_CACHE_SUBJECT_RESULT, KEY_CACHE_MEMBER_SHARE_TIMES, \
    KEY_EXTRACTING_SUBJECT_RULE, KEY_ADMINISTRATIVE_DIVISION
from motorengine import ASC, FacadeO
from motorengine.stages import MatchStage, LookupStage, SortStage


async def get_vehicle_attribute(code):
    """
    获取车型属性信息
    :param code:
    :return:
    """
    if code:
        vehicle_attribute = RedisCache.hmget(KEY_CODE_VEHICLE_ATTRIBUTE, (code,))[0]
        if not vehicle_attribute:
            vehicle_attribute = await VehicleAttribute.find_one(dict(code=code))
            RedisCache.hmset(KEY_CODE_VEHICLE_ATTRIBUTE,
                             {code: pickle.dumps(vehicle_attribute, pickle.HIGHEST_PROTOCOL)})
            return vehicle_attribute
        else:
            return pickle.loads(vehicle_attribute)
    return None


async def get_vehicle_attribute_title(code):
    if code:
        vehicle_attribute = await get_vehicle_attribute(code)
        if vehicle_attribute:
            title = vehicle_attribute.title
            if title:
                return title
    return None


def get_document_needless(document):
    if document and isinstance(document, dict):
        needless = document.get('needless')
        if isinstance(needless, dict):
            return needless
    return {}


async def do_integral_reward(member_cid, source_integral, integral=None):
    if not isinstance(member_cid, str):
        raise ValueError('Parameter member_cid must be a type of str.')
    if source_integral not in SOURCE_MEMBER_INTEGRAL_LIST:
        raise ValueError('Parameter source_integral must in %s.' % str(SOURCE_MEMBER_INTEGRAL_LIST))
    if integral and not isinstance(integral, int):
        raise TypeError('Parameter integral must be type of int.')
    m_integral = integral
    if integral is None:
        integral_source = await MemberIntegralSource.find_one(dict(source=source_integral))
        if integral_source:
            m_integral = integral_source.integral
    if not m_integral:
        m_integral = 0

    member = await Member.get_by_cid(member_cid)
    if member:
        member.integral = (member.integral if member.integral else 0) + m_integral
        member.updated_dt = datetime.datetime.now()

        integral_detail = MemberIntegralDetail(member_cid=member.cid, integral=m_integral, source=source_integral)
        integral_detail.reward_datetime = datetime.datetime.now()
        integral_detail.content = SOURCE_MEMBER_INTEGRAL_DICT.get(source_integral)

        await integral_detail.save()
        await member.save()

        return True, m_integral
    return False, None


async def do_diamond_reward(member: Member, source_diamond, diamond=None):
    if not isinstance(member, Member):
        raise ValueError('Parameter member_cid must be a type of Member.')
    if source_diamond not in SOURCE_MEMBER_DIAMOND_LIST:
        raise ValueError('Parameter source_diamond must in %s.' % str(SOURCE_MEMBER_DIAMOND_LIST))
    if diamond and not isinstance(diamond, int):
        raise TypeError('Parameter diamond must be type of int or long.')
    m_diamond = diamond
    if diamond is None:
        diamond_reward = await GameDiamondReward.find_one(dict(source=source_diamond))
        if diamond_reward:
            m_diamond = diamond_reward.quantity
    if not m_diamond:
        m_diamond = 0

    member.diamond += m_diamond
    member.updated_dt = datetime.datetime.now()

    diamond_detail = MemberDiamondDetail(member_cid=member.cid, diamond=m_diamond)
    diamond_detail.member_cid = member.cid
    diamond_detail.diamond = m_diamond
    diamond_detail.source = source_diamond
    diamond_detail.reward_datetime = datetime.datetime.now()
    diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)

    await diamond_detail.save()
    await member.save()
    return True, m_diamond


async def update_diamond_reward(member_cid, source_diamond, diamond=0):
    diamond_detail = MemberDiamondDetail(member_cid=member_cid, diamond=diamond, source=source_diamond)
    diamond_detail.reward_datetime = datetime.datetime.now()
    diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)

    await diamond_detail.save()


def set_cached_subject_accuracy(subject_code, correct=False):
    """
     # 缓存题目结果便于统计
    :param subject_code: 题目编号
    :param correct: 是否回答正确
    :return:
    """

    if subject_code:
        cache_key = '%s-E' % subject_code
        if correct:
            cache_key = '%s-C' % subject_code
        value = RedisCache.hget(KEY_CACHE_SUBJECT_RESULT, cache_key)
        if not value:
            value = 0
        value = int(value) + 1
        RedisCache.hset(KEY_CACHE_SUBJECT_RESULT, cache_key, value)


def get_cached_subject_accuracy(subject_code):
    """
    获取题目缓存结果
    :param subject_code: 题目编号
    :return: (正确数量， 错误数量)
    """
    if subject_code:
        correct, error = RedisCache.hmget(KEY_CACHE_SUBJECT_RESULT, ('%s-C' % subject_code, '%s-E' % subject_code))
        if not correct:
            correct = 0
        if not error:
            error = 0
        return int(correct), int(error)
    return 0, 0


def set_cache_answer_limit(member_cid, timeout):
    """
    缓存用户答题次数
    :param member_cid: 用户编号
    :param timeout: 超时时间
    :return:
    """
    if member_cid:
        value = RedisCache.get('%s_%s' % (KEY_ANSWER_LIMIT, member_cid))
    if not value:
        value = 0
    value = int(value) + 1
    RedisCache.set('%s_%s' % (KEY_ANSWER_LIMIT, member_cid), value, timeout)


def get_cache_answer_limit(member_cid):
    """
    获取用户答题次数
    :param member_cid:用户CID
    :return: 答题次数
    """
    if member_cid:
        value = RedisCache.get('%s_%s' % (KEY_ANSWER_LIMIT, member_cid))
        if value:
            return int(value)
    return 0


async def update_subject_sub_dimension_status(user_id, status, cid_list):
    """
    更新子维度状态
    :param user_id:更改user id
    :param status:状态
    :param cid_list:子维度cid
    :return:
    """
    if user_id and status and cid_list:

        sub_cid_list = await SubjectDimension.distinct('cid', {'parent_cid': {'$in': cid_list}})
        if sub_cid_list:
            update_requests = []
            for cid in sub_cid_list:
                update_requests.append(UpdateOne({'cid': cid},
                                                 {'$set': {'status': status,
                                                           'updated_dt': datetime.datetime.now(),
                                                           'updated_id': user_id}}))
            await SubjectDimension.update_many(update_requests)


def set_cache_share_times(member_cid, timeout):
    """
    缓存用户分享次數
    :param member_cid: 用户编号
    :param timeout: 超时时间
    :return:
    """
    if member_cid:
        value = RedisCache.get('%s_%s' % (KEY_CACHE_MEMBER_SHARE_TIMES, member_cid))
    if not value:
        value = 0
    value = int(value) + 1
    RedisCache.set('%s_%s' % (KEY_CACHE_MEMBER_SHARE_TIMES, member_cid), value, timeout)


def get_cache_share_times(member_cid):
    """
    获取用户分享次數
    :param member_cid:用户CID
    :return: 分享次數
    """
    if member_cid:
        value = RedisCache.get('%s_%s' % (KEY_CACHE_MEMBER_SHARE_TIMES, member_cid))
        if value:
            return int(value)
    return 0


def set_cache_choice_rule_status_by_cid(rule_cid, value):
    if rule_cid:
        if not value:
            value = 0
        RedisCache.hset(KEY_EXTRACTING_SUBJECT_RULE, rule_cid, value)


async def do_subject_dimension(p_subject_dimension_cid):
    """
    维度变化，检查是否重新抽题
    :param p_subject_dimension_cid:
    :return:
    """
    choice_rule_cursor = SubjectChoiceRules.find(dict(record_flag=1))
    while await choice_rule_cursor.fetch_next:
        choice_rule = choice_rule_cursor.next_object()
        if choice_rule:
            dimension_rules = choice_rule.dimension_rules
            if dimension_rules:
                if dimension_rules.get(p_subject_dimension_cid):
                    set_cache_choice_rule_status_by_cid(choice_rule.cid, 1)


async def set_subject_choice_rules_redis_value(value):
    """
    set抽题规则redis对应的值
    :param value:set的value
    """
    rule_list = await SubjectChoiceRules.find({'record_flag': 1}).to_list(None)
    if rule_list:
        for rule in rule_list:
            RedisCache.hset(KEY_EXTRACTING_SUBJECT_RULE, rule.cid, value)


async def get_administrative_division():
    ad_data = RedisCache.get(KEY_ADMINISTRATIVE_DIVISION)
    if ad_data:
        return msgpack.unpackb(ad_data, raw=False)

    def ad_2_dict(ad):
        result = {}
        if ad:
            if isinstance(ad, (FacadeO, AdministrativeDivision)):
                try:
                    result['code'] = ad.code
                except Exception:
                    result['code'] = ad.post_code
                if not ad.parent_code:
                    result['name'] = ad.title.replace('省', '').replace('市', '').replace('自治区', ''). \
                        replace('壮族', '').replace('回族', '').replace('维吾尔', '')
                else:
                    result['name'] = ad.title
                if ad.parent_code:
                    result['parent_code'] = ad.parent_code
                result['sub'] = []
                if ad.sub_list:
                    for su_ad in ad.sub_list:
                        if su_ad:
                            result['sub'].append(ad_2_dict(su_ad))
            else:
                result['code'] = ad.get('post_code')
                parent_code = ad.get('parent_code')

                if not parent_code:
                    result['name'] = ad.get('title').replace('省', '').replace('市', '').replace('自治区', ''). \
                        replace('壮族', '').replace('回族', '').replace('维吾尔', '')
                else:
                    result['name'] = ad.get('title')

                if parent_code:
                    result['parent_code'] = parent_code
                result['sub'] = []
                sub_list = ad.get('sub_list')
                if sub_list:
                    for su_ad in sub_list:
                        if su_ad:
                            result['sub'].append(ad_2_dict(su_ad))

        return result

    ad_cursor = AdministrativeDivision.aggregate([
        MatchStage(dict(parent_code=None)),
        LookupStage(AdministrativeDivision, as_list_name='sub_list', let=dict(city_parent_code='$post_code'),
                    pipeline=[
                        MatchStage({
                            '$expr': {
                                '$and': [{'$eq': ['$parent_code', '$$city_parent_code']}]
                            }
                        }),
                        SortStage([('post_code', ASC)]),
                        LookupStage(AdministrativeDivision, as_list_name='sub_list',
                                    let=dict(area_parent_code='$post_code'),
                                    pipeline=[
                                        MatchStage({
                                            '$expr': {
                                                '$and': [{'$eq': ["$parent_code", "$$area_parent_code"]}]
                                            }
                                        }),
                                        SortStage([('post_code', ASC)])
                                    ])
                    ]),
        SortStage([('post_code', ASC)])
    ])
    ad_list = []
    while await ad_cursor.fetch_next:
        ad_dict = ad_2_dict(ad_cursor.next_object())
        if ad_dict:
            ad_list.append(ad_dict)
    if ad_list:
        RedisCache.set(KEY_ADMINISTRATIVE_DIVISION, msgpack.packb(ad_list))
    return ad_list


async def do_different_administrative_division(ad_code_list: list):
    """
    区分行政区划等级
    :param ad_code_list: 行政区划编码列表
    :return: (省份, 城市, 区/县)
    """
    province_code_list, city_code_list, district_code_list = [], [], []
    if ad_code_list:
        ad_cursor = AdministrativeDivision.find({'code': {'$in': ad_code_list}})
        while await ad_cursor.fetch_next:
            ad: AdministrativeDivision = ad_cursor.next_object()
            if ad:
                if ad.level == 'P':
                    province_code_list.append(ad.code)
                elif ad.level == 'C':
                    city_code_list.append(ad.code)
                elif ad.level == 'D':
                    district_code_list.append(ad.code)
    return province_code_list, city_code_list, district_code_list


async def do_different_administrative_division2(ad_code_list: list):
    """
    区分行政区划等级
    :param ad_code_list: 行政区划编码列表
    :return: (省份, 城市, 区/县)
    """
    province_code_list, city_code_list, district_code_list = [], [], []

    if not ad_code_list:
        raise ValueError('There are no manageable areas for this account.')

    ad_cursor = AdministrativeDivision.find({'code': {'$in': ad_code_list}})
    while await ad_cursor.fetch_next:
        ad: AdministrativeDivision = ad_cursor.next_object()
        if ad:
            if ad.level == 'P':
                province_code_list.append(ad.code)
                city_code_list += await AdministrativeDivision.distinct('code', {'parent_code': ad.code})
            elif ad.level == 'C':
                city_code_list.append(ad.code)
                province_code_list.append(ad.parent_code)
            elif ad.level == 'D':
                district_code_list.append(ad.code)
    province_code_list.sort()
    city_code_list.sort()
    district_code_list.sort()
    return list(set(province_code_list)), list(set(city_code_list)), list(set(district_code_list))
