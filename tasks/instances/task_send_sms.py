# !/usr/bin/python
# -*- coding:utf-8 -*-



from logger import log_utils
from services.sms_service import send_instant_sms
from tasks import app

logger = log_utils.get_logging('tasks_send_sms', 'tasks_send_sms.log')


@app.task(bind=True)
def send_sms(self, mobile, content):
    if mobile and content:
        status = send_instant_sms(mobile=mobile, msg=content)
        logger.info('[%s] SEND SMS: status=%s, to=%s, content=%s' % (self.request.id, status, mobile, content))
        return status
