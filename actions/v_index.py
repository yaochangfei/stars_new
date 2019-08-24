# !/usr/bin/python
# -*- coding:utf-8 -*-
from settings import SERVER_HOST, RACE_REPORT_HOST
from tornado.web import url
from web import BaseHandler
from tasks.instances.task_send_msg import send_sms

class IndexHandler(BaseHandler):

    def get(self):
        print(self.request.host)
        print(SERVER_HOST)
        # send_sms.delay(mobile=15106139173, content='您的本次验证码为：%s, 有效期%s秒' % ('123456', 100))
        if self.request.host.split(":")[0] == SERVER_HOST:
            self.redirect(self.reverse_url('backoffice_index'))
            return

        if self.request.host == RACE_REPORT_HOST:
            self.redirect(self.reverse_url('frontsite_race_special_login'))
            return


URL_MAPPING_LIST = [
    url(r'/', IndexHandler, name='index'),
]
