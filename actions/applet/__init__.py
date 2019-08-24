# !/usr/bin/python

import datetime

import msgpack
from bson import ObjectId
from caches.redis_utils import RedisCache
from db import STATUS_USER_ACTIVE
from db.models import Member,AppMember
from motorengine import BaseDocument
from pymongo import ReadPreference


def from_msgpack(value):
    """
    还原msgpack数据
    :param value:
    :return:
    """
    if isinstance(value, list):
        for index, v in enumerate(value):
            value[index] = from_msgpack(v)
    if isinstance(value, dict):
        for k, v in value.items():
            if k == 'oid':
                value['_id'] = from_msgpack(v)
            else:
                value[k] = from_msgpack(v)
    if isinstance(value, datetime.datetime):
        value = value.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
    if isinstance(value, str):
        if value.startswith('[DT]'):
            value = datetime.datetime.strptime(value[4:], '%Y-%m-%d %H:%M:%S.%f')
        elif value.startswith('[ID]'):
            value = ObjectId(value[4:])
    return value


def to_msgpack(value):
    """
    值转换成msgpack格式
    :param value:
    :return:
    """
    try:
        if isinstance(value, list):
            for index, v in enumerate(value):
                value[index] = to_msgpack(v)
        if isinstance(value, dict):
            for k, v in value.items():
                value[k] = to_msgpack(v)
        if isinstance(value, datetime.datetime):
            value = '[DT]%s' % value.strftime('%Y-%m-%d %H:%M:%S.%f')
        if isinstance(value, ObjectId):
            value = '[ID]%s' % str(value)
        if isinstance(value, BaseDocument):
            f_map: dict = value.field_mappings
            tv = {}
            for k in f_map.keys():
                if k == 'id':
                    tv['_id'] = to_msgpack(getattr(value, k))
                else:
                    tv[k] = to_msgpack(getattr(value, k))
            value = tv
    except Exception:
        pass
    return value


async def find_member_by_open_id(open_id):
    try:
        member = RedisCache.get(open_id)
        if member:
            member = Member().result_2_obj(from_msgpack(msgpack.unpackb(member, raw=False)))
            return member
    except Exception:
        pass
    member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE),
                                   read_preference=ReadPreference.PRIMARY)
    if member:
        RedisCache.set(open_id, msgpack.packb(to_msgpack(member)), 60 * 60 * 24)
        RedisCache.set('mid_%s' % str(member.oid), open_id, 60 * 60 * 24)
        return member


async def find_app_member_by_cid(cid):
    try:
        member = RedisCache.get(cid)
        if member:
            member = AppMember().result_2_obj(from_msgpack(msgpack.unpackb(member, raw=False)))
            return member
    except Exception:
        pass
    member = await AppMember.find_one(dict(cid=cid),
                                   read_preference=ReadPreference.PRIMARY)
    if member:
        RedisCache.set(cid, msgpack.packb(to_msgpack(member)), 60 * 60 * 24)
        RedisCache.set('mid_%s' % str(member.oid), cid, 60 * 60 * 24)
        return member
#
# async def test():
#     member = await find_member_by_open_id('oSXgn41HaTKKaiF-GqLOSVZcUreE')
#     print(member.__dict__)
#     member.nick_name += '____g'
#     await member.save()
#
#     member = await find_member_by_open_id('oSXgn41HaTKKaiF-GqLOSVZcUreE')
#     print(member.__dict__)
#
#
# task_list = []
# for i in range(1):
#     task_list.append(test())
# loop = asyncio.get_event_loop()
# loop.run_until_complete(asyncio.wait(task_list))
# loop.close()
