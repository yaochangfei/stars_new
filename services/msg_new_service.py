# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import re
import traceback
from submail import submail
from db.models import InstantSms

SEND_MESSAGE_HOST = 'submail'
MOBILE_PATTERN = r"^1\d{10}$"
# 赛邮云通信短信验证码服务
SEND_MOBILE_APP_ID = "40032"  # APPID
SEND_MOBILE_SIGNATURE = "a0d48eaf82ba61458d904ae323bed033"  # APPKEY
SEND_MESSAGE_TEMPLATE_ID = "YYvuS4"  # 短信模版id

STATUS_MOBILE_MSG_SUCCEED = 1  # 发送成功
STATUS_MOBILE_MSG_SYSTEM_ERROR = 0  # 系统异常
STATUS_MOBILE_MSG_NUMBER_NULL = -1  # 手机号为空
STATUS_MOBILE_MSG_NUMBER_ERROR = -2  # 手机号格式错误
STATUS_MOBILE_MSG_CONTENT_NULL = -3  # msg内容为空


def send_instant_sms(mobile, code, time):
    """
    发送文本信息
    @param mobile: 号码
    @param msg: 消息内容
    @return:
    """
    status = STATUS_MOBILE_MSG_SYSTEM_ERROR
    exception = None
    try:
        if not code or not time:
            return STATUS_MOBILE_MSG_CONTENT_NULL
        if not mobile:
            return STATUS_MOBILE_MSG_NUMBER_NULL
        else:
            if not re.match(MOBILE_PATTERN, mobile.strip()):
                return STATUS_MOBILE_MSG_NUMBER_ERROR

        manager = submail.build("sms")
        msg = manager.message()
        msg['appid'] = SEND_MOBILE_APP_ID
        msg['project'] = SEND_MESSAGE_TEMPLATE_ID
        msg['signature'] = SEND_MOBILE_SIGNATURE
        msg['to'] = mobile
        msg['vars'] = {"code": code, "time": time}
        result = msg.send(stype="xsend", inter=False)
        if result.get('status', '') == 'success':
            status = STATUS_MOBILE_MSG_SUCCEED
        else:
            status = result.code
        print(result)

    except Exception:
        exception = traceback.format_exc()

    # 存储发送历史
    try:
        instant_sms = InstantSms(sms_server=SEND_MESSAGE_HOST, account=SEND_MOBILE_APP_ID,
                                 post_dt=datetime.datetime.now(),
                                 status=status, mobile=mobile, content=code, exception=exception)
        instant_sms.sync_save()
    except Exception:
        pass
    return status


if __name__ == '__main__':
    send_instant_sms('15106139173', '123456', '10分钟')
