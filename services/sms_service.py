# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import re
import traceback
from urllib.parse import urlencode
from urllib.request import urlopen

from db.models import InstantSms
from settings import SMS_SIGNATURE

MOBILE_PATTERN = r"^\d{11}$"

SEND_MOBILE_UN = "shzywl-4"
SEND_MOBILE_PWD = "162409"
# SEND_MOBILE_UN = "shzywl-1"
# SEND_MOBILE_PWD = "774ee2"
SEND_MESSAGE_HOST = "http://si.800617.com:4400/SendLenSms.aspx"

STATUS_MOBILE_MSG_SUCCEED = 1  # 发送成功
STATUS_MOBILE_MSG_SYSTEM_ERROR = 0  # 系统异常
STATUS_MOBILE_MSG_NUMBER_NULL = -1  # 手机号为空
STATUS_MOBILE_MSG_NUMBER_ERROR = -2  # 手机号格式错误
STATUS_MOBILE_MSG_CONTENT_NULL = -3  # msg内容为空
STATUS_MOBILE_MSG_CONTENT_LENGTH350_OVER = -4  # msg参数长度超过350个字符
STATUS_MOBILE_MSG_USER_FORBIDDEN = -6  # 发送号码为黑名单用户
STATUS_MOBILE_MSG_CONTENT_FORBIDDEN = -8  # 下发内容中含有屏蔽词
STATUS_MOBILE_MSG_ACCOUNT_NOT_EXIST = -9  # 下发账户不存在
STATUS_MOBILE_MSG_ACCOUNT_DISABLE = -10  # 下发账户已经停用
STATUS_MOBILE_MSG_BALANCE_LACKED = -11  # 下发账户无余额
STATUS_MOBILE_MSG_MD5_CHECK_ERROR = -15  # MD5校验错误
STATUS_MOBILE_MSG_SERVER_AUTH_ERROR = -16  # IP服务器鉴权错误
STATUS_MOBILE_MSG_PORT_TYPE_ERROR = -17  # 接口类型错误
STATUS_MOBILE_MSG_SERVICE_TYPE_ERROR = -18  # 服务类型错误
STATUS_MOBILE_MSG_SEND_THRESHOLD_OVER = -22  # 手机号达到当天发送限制
STATUS_MOBILE_MSG_SS_SEND_THRESHOLD_OVER = -23  # 同一手机号，相同内容达到当天发送限制


def send_instant_sms(mobile, msg):
    """
    发送文本信息
    @param mobile: 号码
    @param msg: 消息内容
    @return:
    """
    status = STATUS_MOBILE_MSG_SYSTEM_ERROR
    exception = None
    try:
        if not msg:
            return STATUS_MOBILE_MSG_CONTENT_NULL
        if not mobile:
            return STATUS_MOBILE_MSG_NUMBER_NULL
        else:
            if not re.match(MOBILE_PATTERN, mobile.strip()):
                return STATUS_MOBILE_MSG_NUMBER_ERROR
        # 内容添加签名
        msg = '%s %s' % (SMS_SIGNATURE, msg)
        params = urlencode(
            {'un': SEND_MOBILE_UN, 'pwd': SEND_MOBILE_PWD, 'msg': msg.encode('gb2312'), 'mobile': mobile})
        res = urlopen('%s?%s' % (SEND_MESSAGE_HOST, params)).read()
        status = get_result(res)
    except Exception:
        exception = traceback.format_exc()

    # 存储发送历史
    try:
        instant_sms = InstantSms(
            sms_server=SEND_MESSAGE_HOST, account=SEND_MOBILE_UN, post_dt=datetime.datetime.now(), status=status,
            mobile=mobile, content=msg, exception=exception)
        instant_sms.sync_save()
    except Exception:
        pass
    return status


def get_result(text):
    """
    获取短信息发送结果
    :param text:
    :return:
    """
    try:
        result_pat = r'<Result>(\d+)</Result>'
        ret = re.search(result_pat, text.decode('utf-8'))
        if ret:
            return int(ret.groups(0)[0])
    except Exception:
        pass
    return None
