# !/usr/bin/python
# -*- coding:utf-8 -*-

import json

from commons.request_utils import do_http_request
from logger import log_utils

logger = log_utils.get_logging()


async def check_lsm_verify_code(vcode):
    """
    螺丝帽验证
    :param vcode: 验证码
    :return: 检查结果
    """
    data = {
        'api_key': 'e54004ba7fd0f62432fe5da296426a09',
        'response': vcode,
    }
    r = await do_http_request(url='https://captcha.luosimao.com/api/site_verify', method='POST', body=json.dumps(data))
    result = json.loads(r.body)
    if result.get('res') == 'failed':
        return False
    return True
