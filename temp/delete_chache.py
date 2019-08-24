#! /usr/bin/python

"""
删除报表缓存

"""
import subprocess
from caches.redis_utils import RedisCache


def delete_tendency_cache():
    with open('logs/cache.log') as f:
        for line in f.readlines():
            if 'Tendency' in line:
                cache_key = line.split(' ')[-1].replace('\n', '')
                RedisCache.delete(cache_key)
                print('has delete %s, and get it : %s' % (cache_key, RedisCache.get(cache_key)))


def delete_all_caches():
    RedisCache.delete('KEY_CACHE_REPORT_ECHARTS_CONDITION')
    cmd = "cat logs/cache.log* | awk '{print $6}'"
    _, caches = subprocess.getstatusoutput(cmd)
    for cache_key in caches.split('\n'):
        RedisCache.delete(cache_key)
        print('has delete %s, and get it : %s' % (cache_key, RedisCache.get(cache_key)))


if __name__ == '__main__':
    # delete_all_caches()
    pass
