# !/usr/bin/python
# -*- coding:utf-8 -*-

from logger import log_utils

logger = log_utils.get_logging()


class RequestMiddleware(object):

    def before_request_hook(self):
        """
        执行GET, POST等等request方法前执行
        :return:
        """
        pass

    def before_response_hook(self):
        """
        开始response之前执行
        :return:
        """
        pass

    def after_response_hook(self):
        """
        完成response之后执行
        :return:
        """
        pass

    def get_request_handler(self):
        """
        获取请求句柄
        :return:
        """
        return getattr(self, '_handler')

    @property
    def current_user(self):
        return self.get_request_handler().get_current_user()
