# !/usr/bin/python
# -*- coding:utf-8 -*-


from caches.redis_utils import RedisCache
from enums import KEY_EXTRACTING_SUBJECT_RULE


def get_subject_extract_tip_show_status():
    """
    获取题库更新提示状态
    :return:
    """
    cached_extract_dict = RedisCache.hgetall(KEY_EXTRACTING_SUBJECT_RULE)
    for status in cached_extract_dict.values():
        if status in [1, b'1']:
            return True
    return False
