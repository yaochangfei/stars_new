# !/usr/bin/python
# -*- coding:utf-8 -*-


from logger import log_utils
from services.msg_new_service import send_instant_sms
from tasks import app

logger = log_utils.get_logging('tasks_send_msg_new', 'tasks_send_msg_new.log')


@app.task(bind=True, queue='send_msg_new')
def send_msg_new(self, mobile, code, time):
    print(mobile)
    print(code)
    print(time)
    if mobile and code and time:
        logger.info('START: Send SMS mobile=%s, code=%s' % (mobile, code))
        status = send_instant_sms(mobile=mobile, code=code, time=time)
        print(status, 'status')
        logger.info('[%s] SEND SMS: status=%s, to=%s, code=%s' % (self.request.id, status, mobile, code))
        return status
