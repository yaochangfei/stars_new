# !/usr/bin/python
# -*- coding:utf-8 -*-



import copy
import datetime

import msgpack
from bson import ObjectId

from caches.redis_utils import RedisCache
from motorengine import BaseDocument
import settings


class MotorCacheEngine(object):
    """
    单例
    """

    __enable = 0
    __database = None
    __redis = None

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls.instance = super(MotorCacheEngine, cls).__new__(cls)
        return cls.instance

    @property
    def enable(self):
        """
        缓存是否有效
        :return:
        """
        return self.__enable

    def initialize(self):
        """
        初始化缓存
        :return:
        """
        db_name = self.db_name
        if db_name:
            if settings.OPT_DISTRIBUTED_CACHED_ENABLE:
                try:
                    self.__redis = RedisCache
                    self.__enable = 1
                except Exception:
                    self.__enable = -1
                    print('Warning: Redis connection pool create failed, disabled DB cache!')
            else:
                self.__enable = -1

    @property
    def db_name(self):
        """
        当前数据库名
        :return:
        """
        if self.__database:
            return self.__database.name
        return ''

    def switch_db(self, database=None):
        """
        切换数据库
        :param database: 数据库
        :return:
        """
        self.__database = database

    def get(self, name, default=None):
        """
        从缓存中获取值
        :param name: 缓存名称
        :param default: 默认值
        :return:
        """
        if name:
            if self.db_name:
                cache_data = self.__redis.get('%s.%s' % (self.db_name, name))
                if cache_data:
                    try:
                        return self.__from_msgpack(msgpack.unpackb(cache_data, raw=False))
                    except Exception as e:
                        raise e
        return default

    def set(self, name, value=None, timeouts=2 * 60 * 60):
        """
        值放入缓存
        :param name: 缓存名称
        :param value: 缓存值
        :param timeouts: 超时时间
        :return:
        """
        if name:
            if self.db_name:
                try:
                    cache_data = msgpack.packb(self.__to_msgpack(copy.deepcopy(value)))
                    if cache_data:
                        self.__redis.set('%s.%s' % (self.db_name, name), cache_data, timeout=timeouts)
                        return True
                except Exception as e:
                    print(e)
        return False

    def delete(self, name):
        """
        删除缓存
        :param name: 缓存名
        :return:
        """
        if name:
            if self.db_name:
                self.__redis.delete('%s.%s' % (self.db_name, name))
                return True
        return False

    def delete_many(self, name_list: list or tuple):
        """
        批量删除缓存
        :param name_list: 多个缓存名
        :return:
        """
        if name_list:
            k_list = ['%s.%s' % (self.db_name, name) for name in name_list]
            self.__redis.db.delete(*k_list)
            return True
        return False

    def contain(self, name):
        """
        判断缓存是否存在
        :param name: 缓存名
        :return:
        """
        if name and self.db_name:
            return self.__redis.db.exists('%s.%s' % (self.db_name, name))
        return False

    def __from_msgpack(self, value):
        """
        还原msgpack数据
        :param value:
        :return:
        """
        if isinstance(value, list):
            for index, v in enumerate(value):
                value[index] = self.__from_msgpack(v)
        if isinstance(value, dict):
            for k, v in value.items():
                if k == 'oid':
                    value['_id'] = self.__from_msgpack(v)
                else:
                    value[k] = self.__from_msgpack(v)
        if isinstance(value, datetime.datetime):
            value = value.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
        if isinstance(value, str):
            if value.startswith('[DT]'):
                value = datetime.datetime.strptime(value[4:], '%Y-%m-%d %H:%M:%S.%f')
            elif value.startswith('[ID]'):
                value = ObjectId(value[4:])
        return value

    def __to_msgpack(self, value):
        """
        值转换成msgpack格式
        :param value:
        :return:
        """
        try:
            if isinstance(value, list):
                for index, v in enumerate(value):
                    value[index] = self.__to_msgpack(v)
            if isinstance(value, dict):
                for k, v in value.items():
                    value[k] = self.__to_msgpack(v)
            if isinstance(value, datetime.datetime):
                value = '[DT]%s' % value.strftime('%Y-%m-%d %H:%M:%S.%f')
            if isinstance(value, ObjectId):
                value = '[ID]%s' % str(value)
            if isinstance(value, BaseDocument):
                f_map: dict = value.field_mappings
                tv = {}
                for k in f_map.keys():
                    if k == 'id':
                        tv['_id'] = self.__to_msgpack(getattr(value, k))
                    else:
                        tv[k] = self.__to_msgpack(getattr(value, k))
                value = tv
        except Exception:
            pass
        return value


CacheEngine = MotorCacheEngine()
