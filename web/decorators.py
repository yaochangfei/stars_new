# !/usr/bin/python
# -*- coding:utf-8 -*-
import json

from commons import menu_utils
from commons.common_utils import ComplexJsonEncoder


class ResultData(object):
    """
    数据结果
    """

    def __init__(self, code=0, **kwargs):
        self.code = code
        self.kwargs = kwargs

    @property
    def data(self):
        result = {}
        result.update(vars(self))
        result.update(self.kwargs)
        result.__delitem__('kwargs')
        return result

    def __setitem__(self, key, value):
        setattr(self, key, value)

    def __repr__(self):
        return str(self.data)

    def __str__(self):
        return str(self.data)


def render_template(template_name):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            data = await func(self, *args, **kwargs)
            if not isinstance(data, dict):
                return data
            if 'self' in data.keys():
                del data['self']
            if self.request.path.startswith('/backoffice'):
                user_menu = await menu_utils.get_user_menu(self, menu_key='backend')
                data['user_menu'] = user_menu
            tmpl = template_name
            if tmpl:
                tmpl = data.pop('TEMPLATE', tmpl)

            if not data.get('dark_skin'):
                data['dark_skin'] = None
            self.render(tmpl, **data)

        return wrapper

    return decorator


def render_json(func):
    async def wrapper(self, *args, **kwargs):
        data = await func(self, *args, **kwargs)
        if not isinstance(data, dict):
            return data
        if 'self' in data.keys():
            del data['self']
        self.write(json.dumps(data, cls=ComplexJsonEncoder))

    return wrapper


def authenticated(func):
    async def wrapper(self, *args, **kwargs):
        if not self.current_user:
            if self.request.method in ("GET", "HEAD"):
                to_url = '/'
                if self.request.path.startswith('/backoffice'):
                    to_url = self.reverse_url('backoffice_index')
                elif self.request.path.startswith('/frontsite'):
                    to_url = self.reverse_url('login')
                self.render('forbidden.html', **{'forbidden_code': 1, 'to_url': to_url})
                return
        result = await func(self, *args, **kwargs)
        return result

    return wrapper


def permission_required(perm_code):
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            current_user = self.current_user
            if current_user:
                passed = await current_user.has_perm(perm_code)
                if passed:
                    data = await func(self, *args, **kwargs)
                    return data
                else:
                    to_url = '/'
                    if self.request.path.startswith('/backoffice'):
                        to_url = self.reverse_url('backoffice_index')
                    self.render('forbidden.html', forbidden_code=2, to_url=to_url)
            else:
                to_url = '/'
                if self.request.path.startswith('/backoffice'):
                    to_url = self.reverse_url('backoffice_index')
                self.render('forbidden.html', forbidden_code=1, to_url=to_url)

        return wrapper

    return decorator


def restful_validation(func):
    async def wrapper(self, *args, **kwargs):
        if not self.access_token:
            self.write(str({'code': 1001}))
        elif not self.client_timestamp:
            self.write(str({'code': 1002}))
        elif not self.signature:
            self.write(str({'code': 1003}))
        elif not self.i_args:
            self.write(str({'code': 1004}))
        else:
            return await func(self, *args, **kwargs)

    return wrapper


def wechat_applet_authenticated(func):
    async def wrapper(self, *args, **kwargs):
        if not self.get_i_argument('access_token'):
            # 没有Access Token
            self.write(str({'code': -1}))
        elif not self.get_i_argument('timestamp'):
            # 没有时间戳
            self.write(str({'code': -2}))
        elif not self.get_i_argument('signature'):
            # 没有签名或签名错误
            self.write(str({'code': -3}))
        else:
            return await func(self, *args, **kwargs)

    return wrapper
