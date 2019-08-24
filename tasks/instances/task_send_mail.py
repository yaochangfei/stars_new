# !/usr/bin/python
# -*- coding:utf-8 -*-


from logger import log_utils
from services.email_service import send_instant_mail
from tasks import app

logger = log_utils.get_logging('tasks_send_mail', 'tasks_send_mail.log')


@app.task(bind=True)
def send_mail(self, mail_to: list = None, subject: str = '提醒', content: str = '', content_images: dict = None,
              attachments: list = None):
    status = send_instant_mail(mail_to=mail_to, subject=subject, content=content, content_images=content_images,
                               attachments=attachments)
    logger.info('[%s] SEND MAIL: status=%s, to=%s, subject=%s' % (self.request.id, status, mail_to, subject))
    return status
