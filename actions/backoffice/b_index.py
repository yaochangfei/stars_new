# !/usr/bin/python
# -*- coding:utf-8 -*-
from tornado.web import url

from web import BaseHandler


class IndexHandler(BaseHandler):

    async def get(self):
        self.redirect(self.reverse_url('backoffice_login'))


URL_MAPPING_LIST = [
    url(r'/backoffice/', IndexHandler, name='backoffice_index')
]
