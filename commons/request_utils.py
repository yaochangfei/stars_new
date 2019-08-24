# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback

from tornado.httpclient import AsyncHTTPClient, HTTPRequest, HTTPError

from logger import log_utils

logger = log_utils.get_logging()


async def do_http_request(url, method='GET', headers=None, body=None, request_timeout=10, **kwargs):
    """
    发送异步请求
    :param url: 请求URL
    :param method: 请求方法
    :param headers: 请求附属数据
    :param body: 请求附属数据
    :param request_timeout: 超时时间
    :param kwargs: 其他参数
    :return:
    """
    if not isinstance(url, str):
        raise ValueError('"url" must be a str.')
    if not (url.lower().startswith('http://') or url.lower().startswith('https://')):
        raise ValueError('"url" not a valid URL.')

    request = HTTPRequest(url, method=method, headers=headers, body=body, request_timeout=request_timeout,
                          validate_cert=False, **kwargs)
    http_client = AsyncHTTPClient()
    try:
        response = await http_client.fetch(request)
        if response:
            return response
    except HTTPError:
        logger.error(traceback.format_exc())
    return None
