# !/usr/bin/python
# -*- coding:utf-8 -*-

import redis
from redis import StrictRedis
from rediscluster import StrictRedisCluster

import settings


class RedisDB(object):
    __redis_cluster = None

    def __init__(self):
        pass

    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, '_instance'):
            cls._instance = super(RedisDB, cls).__new__(cls, *args, **kwargs)
            cls._cluster = settings.REDIS_CLUSTER
            cls._startup_nodes = settings.REDIS_NODES
            if cls._cluster:
                if not cls._startup_nodes:
                    raise ValueError('Redis cluster nodes not specified.')
        return cls._instance

    @property
    def __rc(self):
        if not self.__redis_cluster:
            if self._cluster:
                startup_nodes = []
                for node in self._startup_nodes:
                    if node:
                        host, port = node.split(':')
                        if not host or not port:
                            raise ValueError('Redis cluster nodes host error.')
                        startup_nodes.append({'host': host, 'port': port})
                if not startup_nodes:
                    raise ValueError('Redis cluster nodes not specified.')
                self.__redis_cluster = StrictRedisCluster(
                    startup_nodes=startup_nodes, **settings.REDIS_OPTIONS)

            else:
                default_node = self._startup_nodes[0]
                if not default_node:
                    raise ValueError('Redis server node not specified.')
                host, port = default_node.split(':')
                if not host:
                    raise ValueError('Redis server host not specified.')
                if not port:
                    port = 6379
                connection_pool = redis.ConnectionPool(host=host, port=port)
                self.__redis_cluster = StrictRedis(
                    connection_pool=connection_pool, **settings.REDIS_OPTIONS)

        return self.__redis_cluster

    @property
    def db(self):
        return self.__rc

    def set(self, name, value=None, timeout=None):
        """
        设置值
        :param name: 键
        :param value: 值
        :param timeout: 超时时间，None 时永不超时
        :return:
        """
        self.__rc.set(name, value, ex=timeout)

    def get(self, name):
        """
        获取值
        :param name: 键
        :return: 从Redis获取到的值
        """
        val = self.__rc.get(name)
        if isinstance(val, bytes):
            try:
                return val.decode('utf-8')
            except Exception:
                pass
        return val

    def delete(self, name):
        """
        删除值
        :param name: 键
        :return:
        """
        self.__rc.delete(name)

    def mset(self, **kwargs):
        """
        批量设值
        :param kwargs: 参数列表（key-value）
        :return:
        """
        self.__rc.mset(**kwargs)

    def mget(self, names):
        """
        批量获取值
        :param keys: 键列表，List或Tuple
        :return: 返回对应值， List或Tuple，与参数形式对应
        """
        return self.__rc.mget(names)

    def hset(self, name, key, value=None):
        """
        设置一个dict形式的值
        :param name: 键
        :param key: 值键
        :param value: 值
        :return:
        """
        self.__rc.hset(name, key, value)

    def hget(self, name, key):
        """
        获取一个dict形式的值
        :param name: 键
        :param key: 值键
        :return:
        """
        return self.__rc.hget(name, key)

    def hmset(self, name, kv_dict=None):
        """
        批量设置dict形式的值
        :param name: 键
        :param kv_dict: 值(dict)
        :return:
        """
        self.__rc.hmset(name, kv_dict)

    def hmget(self, name, keys):
        """
        批量获取dict形式的值
        :param name: 键
        :param keys: 值键List或Tuple，与参数形式对应
        :return:
        """
        return self.__rc.hmget(name, keys)

    def hgetall(self, name):
        """
        获取dict形式所有的值
        :param name:
        :return:
        """
        return self.__rc.hgetall(name)

    def hlen(self, name):
        """
        获取dict形式值的个数
        :param name: 键
        :return:
        """
        return self.__rc.hlen(name)

    def hkeys(self, name):
        """
        获取dict形式所有的键
        :param name: 键
        :return:
        """
        return self.__rc.hkeys(name)

    def hvals(self, name):
        """
        获取dict形式所有的值
        :param name: 键
        :return:
        """
        return self.__rc.hvals(name)

    def hexists(self, name, key):
        """
        判断值键是否存在
        :param name:
        :param key:
        :return:
        """
        return self.__rc.hexists(name, key)

    def hdel(self, name, *keys):
        """
        获取dict形式多个key
        :param name: 键
        :param keys: 值键Tuple
        :return:
        """
        self.__rc.hdel(name, *keys)

    def lpush(self, name, *vals):
        """
        元素追加到列表
        :param name: 键
        :param vals: 多个值
        :return:
        """
        self.__rc.rpush(name, *vals)

    def lget(self, name, index):
        """
        取指定位置的值
        :param name: 键
        :param index: 索引值
        :return:
        """
        return self.__rc.lindex(name, index)

    def llen(self, name):
        """
        取list的大小
        :param name:
        :return:
        """
        return self.__rc.llen(name)

    def lpop(self, name):
        """

        :param name:
        :return:
        """
        return self.__rc.lpop(name)

    def ldel(self, name, value):
        """
        删除值
        :param name: 键
        :param value: 值
        :return:
        """
        self.__rc.lrem(name, value)

    def sadd(self, name, vals):
        """
        想集合中添加元素
        :param name: 键
        :param vals: 多个值
        :return:
        """
        self.__rc.sadd(name, vals)

    def slen(self, name):
        """
        获取集合元素个数
        :param name: 键
        :return: 集合长度
        """
        return self.__rc.scard(name)

    def smembers(self, name):
        """
        获取集合所有成员
        :param name: 键
        :return: 所有成员
        """
        return self.__rc.smembers(name)

    def sinmembers(self, name, value):
        """
        判断值是否存在与集合中
        :param name: 键
        :param value: 值
        :return:
        """
        return self.__rc.sismember(name, value)

    def sdel(self, name):
        """
        从集合中删除成员
        :param name:
        :return:
        """
        self.__rc.spop(name)


RedisCache = RedisDB()
