# !/usr/bin/python
# -*- coding:utf-8 -*-
import base64
import copy
import hashlib
import hmac
import itertools
import json
import random
from json import JSONEncoder

import time
import datetime

import os
from io import BytesIO
import requests
from contextlib import closing
from bs4 import BeautifulSoup
from bson import ObjectId
from encoder import XML2Dict
import settings
from PIL import Image

# 解析JSON特殊数据类型
from caches.redis_utils import RedisCache
from motorengine.base import BaseDocument
from wechat.enums import QR_GET_ACCESS_TOKEN_URL, QR_POST_URL


class ComplexJsonEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime.datetime):
            return obj.strftime('%Y-%m-%d %H:%M:%S.%f')
        elif isinstance(obj, BaseDocument):
            return vars(obj)
        elif isinstance(obj, bytes):
            return obj.decode('utf-8')

        return JSONEncoder.default(self, obj)


def string(b_str: bytes):
    if isinstance(b_str, bytes):
        return b_str.decode('utf-8')
    return str(b_str)


def strip_tags(html):
    """
    删除文本中所有的HTML标签
    :param html: 文本
    :return:
    """
    data = ''
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        data = soup.get_text()
    return data


def md5(a_string):
    """
    生成MD5
    :param a_string: 对照
    :return:
    """
    if not isinstance(a_string, (bytes, str)):
        pass
    if isinstance(a_string, str):
        a_string = a_string.encode('utf-8')
    return hashlib.md5(a_string).hexdigest()


def h_mac(key, msg=None, digestmod=None):
    if isinstance(key, str):
        key = key.encode('utf-8')
    if isinstance(msg, str):
        msg = msg.encode('utf-8')
    if isinstance(digestmod, str):
        digestmod = digestmod.encode('utf-8')

    return hmac.new(key, msg, digestmod).hexdigest()


def sha1(a_string):
    if isinstance(a_string, str):
        a_string = a_string.encode('utf-8')
    return hashlib.sha1(a_string).hexdigest()


def sha256(a_string):
    if isinstance(a_string, str):
        a_string = a_string.encode('utf-8')
    return hashlib.sha256(a_string).hexdigest()


def base64encode(value):
    """
    给予Base64对值进行加密
    :param value: 传入值
    :return: 加密结果
    """
    if value:
        if isinstance(value, str):
            value = value.encode('utf-8')
        return base64.b64encode(value)
    return None


def base64decode(value):
    """
    给予Base64对值进行解密
    :param value: 传入已加密值
    :return: 解密结果
    """
    if value:
        if isinstance(value, str):
            value = value.encode('utf-8')
        return base64.b64decode(value)
    return None


def str2datetime(datetime_str, date_format='%Y-%m-%d %H:%M:%S'):
    """
    日期字符串转换成日期
    :param datetime_str: 日期字符串
    :param date_format: 日期格式
    :return: 日期
    """
    if datetime_str:
        try:
            return datetime.datetime.strptime(datetime_str, date_format)
        except ValueError:
            return datetime.datetime.strptime(datetime_str, '%Y-%m-%d')
    return None


def datetime2str(date_time, date_format='%Y-%m-%d %H:%M:%S'):
    """
    日期转换成字符串
    :param date_time: 日期
    :param date_format: 日期格式
    :return: 日期字符串
    """
    if date_time:
        return date_time.strftime(date_format)
    return None


def datetime2timestamp(date_time):
    """
    日期转换成时间戳
    :param date_time: 日期
    :return: 时间戳
    """
    if date_time:
        return time.mktime(time.strptime(date_time.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S'))
    return None


def timestamp2datetime(timestamp):
    """
    时间戳转换成日期
    :param timestamp: 时间戳
    :return: 日期
    """
    if timestamp:
        return datetime.datetime.strptime(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp)),
                                          '%Y-%m-%d %H:%M:%S')
    return None


def timestamp2str(timestamp, date_format='%Y-%m-%d %H:%M:%S'):
    """
    时间戳转换成字符串
    :param timestamp:
    :param date_format:
    :return:
    """
    if timestamp:
        return datetime2str(timestamp2datetime(timestamp), date_format)
    return None


def str2timestamp(datetime_str, date_format='%Y-%m-%d %H:%M:%S'):
    """
    字符串转换成时间戳
    :param datetime_str:
    :param date_format:
    :return:
    """
    if datetime_str:
        return datetime2timestamp(str2datetime(datetime_str, date_format))
    return None


def read_json_resource(json_file):
    """
    读取资源文件JSON
    :param json_file: 文件名
    :return:
    """
    if not isinstance(json_file, (bytes, str)):
        raise ValueError('Parameter json_file must be not None and type of str or unicode.')
    json_path = os.path.join(settings.SITE_ROOT, 'res', json_file)
    if os.path.exists(json_path):
        with open(json_path, 'rt', encoding='utf-8') as jf:
            json_s = jf.read()
            menu_dict = json.loads(json_s)
            if menu_dict:
                return json.loads(json_s)
    return None


def write_file_by_meta(file_meta, file_path, rename=True, extension_list=None):
    """

    :param file_meta: 上传的元文件信息
    :param file_path: 需要保存的文件位置
    :param rename: 是否重命名
    :param extension_list: 后缀名检查
    :return:
    """
    res = dict(code=0)
    buffers = []
    full_file_name = file_meta['filename']
    extension = os.path.splitext(full_file_name)[-1]
    file_name = ''.join(os.path.splitext(full_file_name)[:-1])
    if extension_list is not None:
        # 校验文件扩展名
        if extension not in extension_list:
            res['code'] = -1
    else:
        # 重命名文件名
        if rename:
            file_name = md5('%s%s' % (file_name, datetime.datetime.now().strftime('%Y%m%d%H%M%S%f'))).upper()

        current_file_path = os.path.join(file_path, '%s%s' % (file_name, extension))
        buffers.append(file_meta['body'])
        if not os.path.exists(file_path):
            os.mkdir(file_path)

        with open(current_file_path, 'wb') as f:
            f.write(b''.join(buffers))

        res['code'] = 1
        res['file_name'] = '%s%s' % (file_name, extension)
    return res


def get_random_str(size=32):
    """
    获取定长随机字符串
    :param size: 结果长度
    :return: 随机字符串
    """
    seed_str = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ=_' * 16
    return ''.join(random.sample(seed_str, size))


def get_file_extension_name(file_name=''):
    """
    获取文件扩展名
    :param file_name: 文件名或路径
    :return:
    """
    return os.path.splitext(file_name)[1]


async def drop_disk_file(path):
    if os.path.exists(path):
        os.remove(path)


def xml2dict(xml):
    """
    将xml转换成dict
    :param xml: xml格式字符串
    :return:
    """
    return XML2Dict().parse(xml).get('xml')


def get_increase_code(key, begin=10000000):
    """
    获取增长的code键值
    :param key:
    :param begin:
    :return:
    """
    value = RedisCache.get(key)
    if value:
        value = str(int(value) + 1)
        RedisCache.set(key, value)
    else:
        value = str(begin + 1)
        RedisCache.set(key, value)
    return value


def float2str(value):
    if isinstance(value, float):
        return str(int(value))
    return value


def combination(*elements) -> list:
    """
    交叉组合所有数组
    :param elements:
    :return:
    """
    result_list = []
    # 一次组合
    permuted_list = []
    for element in elements:
        permuted_list.append([list(result) for result in itertools.permutations(element, len(element))])
    # 二次组合
    twice_permuted_list = list(itertools.permutations(permuted_list, len(permuted_list)))
    for permuted_list in twice_permuted_list:
        tmp_list = []
        length = len(permuted_list)
        if length > 1:
            index = 1
            while True:
                if index == 1:
                    tmp_list = combined_two_list(permuted_list[index - 1], permuted_list[index])
                else:
                    tmp_list = combined_two_list(tmp_list, permuted_list[index])
                index += 1
                if index >= length:
                    break
        elif length == 1:
            tmp_list = (permuted_list[0],)

        if tmp_list:
            result_list.extend(tmp_list)

    return result_list


def combined_two_list(first_list: list, second_list: list):
    """
    交叉两个数组
    :param first_list: 数组一
    :param second_list: 数组二
    :return:
    """
    result_list = []
    if first_list and second_list:
        for first in first_list:
            for second in second_list:
                if isinstance(first, tuple):
                    # print(first, second)
                    tmp = list(copy.deepcopy(first))
                    tmp.append(second)
                    result_list.append(tmp)
                else:
                    result_list.append((first, second))
    # print(result_list)
    return result_list


async def download_qr_image(name=None, page='pages/index/index', scene=''):
    """

    :param name: 文件名
    :param path: 扫描二维码时需要调转的路径
    :return: 文件名
    """
    if not name:
        raise Exception('the download QR filename must be assigned.')

    res = requests.get(QR_GET_ACCESS_TOKEN_URL)
    if res.status_code != 200:
        raise Exception('get token request failed')

    token = json.loads(res.text).get('access_token')
    qr_post_url = QR_POST_URL.format(token=token)

    post_param = json.dumps({
        'scene': scene,
        'page': page,
        'auto_color': True,
        'is_hyaline': False
    })

    file_path = settings.STATIC_PATH + '/files/' + name
    post_res = requests.post(qr_post_url, data=post_param)
    with closing(post_res) as response:
        b_io = BytesIO(response.content)
        Image.open(b_io).save(file_path, format='PNG')
