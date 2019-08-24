# !/usr/bin/python
# -*- coding:utf-8 -*-
import json

import datetime

from caches.redis_utils import RedisCache
from web.plugins import RequestMiddleware


class VerificationCodeLimitMiddleware(RequestMiddleware):

    def before_request_hook(self):
        if self.validate():
            handler = self.get_request_handler()
            mobile = handler.get_argument('mobile')
            if mobile:
                times = RedisCache.get('hook_%s' % str(mobile))
                if times and int(times) > 500:
                    handler.write('{"code": -1}')
                    handler.finish()

    def before_response_hook(self):
        if self.validate():
            handler = self.get_request_handler()
            mobile = handler.get_argument('mobile')
            if mobile:
                result = handler._write_buffer
                if result:
                    if isinstance(result[0], bytes):
                        result = json.loads(result[0].decode('utf-8'))
                    else:
                        result = json.loads(result[0])
                    if result['code'] == 1:
                        times = RedisCache.get('hook_%s' % str(mobile))
                        if not times:
                            times = 0
                        RedisCache.set('hook_%s' % str(mobile), int(times) + 1, self.__get_today_remain_seconds())

    def validate(self):
        return self.get_request_handler().request.path.startswith('/common/mobile_validate/')

    def __get_today_remain_seconds(self):
        last_time = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        return (last_time - datetime.datetime.now()).seconds
