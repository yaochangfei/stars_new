# !/usr/bin/python
# -*- coding:utf-8 -*-



from logger import log_utils
from services.msg_service import send_instant_sms
from tasks import app

logger = log_utils.get_logging('tasks_send_sms')


@app.task(bind=True, queue='send_msg')
def send_sms(self, mobile, content):
    print(mobile)
    print(content)
    if mobile and content:
        logger.info('START: Send SMS mobile=%s, content=%s' % (mobile, content))
        status = send_instant_sms(mobile=mobile, msg=content)
        print(status, 'status')
        logger.info('[%s] SEND SMS: status=%s, to=%s, content=%s' % (self.request.id, status, mobile, content))
        return status