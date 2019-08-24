# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import json
import os
from importlib import import_module
from json import JSONDecodeError

from tornado import options
from tornado.web import Application, RequestHandler

from caches.redis_utils import RedisCache
from commons.common_utils import strip_tags, datetime2str, base64decode, datetime2timestamp, md5
from enums import KEY_SESSION_USER, KEY_MEMBER_CODE
from settings import SITE_ROOT
from web import session
from web.plugins import RequestMiddleware


class IBApplication(Application):

    def __init__(self, default_host=None, transforms=None, **settings):
        session_secret = settings.get('session_secret')
        session_timeout = settings.get('session_timeout')
        if session_timeout and session_secret:
            self.session_manager = session.SessionManager(session_secret, session_timeout)
        else:
            raise RuntimeError('No session information set')
        Application.__init__(self, default_host=default_host, transforms=transforms, **settings)

    def register_handlers(self):
        for root, dirs, files in os.walk(os.path.join(SITE_ROOT, 'actions')):
            for file_name in files:
                if file_name.endswith('.py') or file_name.endswith('.PY'):
                    module = self._path_2_module(os.path.join(root, file_name))
                    if module:
                        module = import_module(module)
                        if hasattr(module, 'URL_MAPPING_LIST'):
                            self.add_handlers('.*$', module.URL_MAPPING_LIST)

    def _path_2_module(self, path=''):
        if path:
            module = path.replace('\\', '/').replace(SITE_ROOT.replace('\\', '/'), '')
            if module.startswith('/'):
                module = module[1:]
            module = module.replace('/', '.').replace('.py', '').strip()
            if module:
                return module
        return None


class BaseMiddlewareHandler(RequestHandler):

    def __init__(self, application, request, **kwargs):
        super(BaseMiddlewareHandler, self).__init__(application, request, **kwargs)

        self.all_middleware_list = []
        self.__parse_middleware()

    def __parse_middleware(self):
        if options.options.request_handler_middleware:
            for s_module in options.options.request_handler_middleware:
                module_name, class_name = self.__separate_module(s_module)
                module = import_module(module_name)
                if module:
                    self.all_middleware_list.append(self.__create_class_with_handler(getattr(module, class_name)))

    def __separate_module(self, s_module: str):
        if s_module:
            try:
                pos = s_module.rindex('.')
                return s_module[:pos], s_module[pos + 1:]
            except ValueError:
                raise ValueError('%s is not a valid module path.' % s_module)
        else:
            raise ValueError('%s must not empty.' % s_module)

    def __create_class_with_handler(self, cls):
        new_class = cls()
        if not isinstance(new_class, RequestMiddleware):
            raise TypeError('"%s" must a instance of web.plugins.middleware.RequestMiddleware.')
        new_class._handler = self
        return new_class

    def prepare(self):
        for middleware in self.all_middleware_list:
            middleware.before_request_hook()

    def finish(self, chunk=None):
        for middleware in self.all_middleware_list:
            middleware.before_response_hook()
        super(BaseMiddlewareHandler, self).finish(chunk)

    def on_finish(self):
        for middleware in self.all_middleware_list:
            middleware.after_response_hook()


class BaseHandler(BaseMiddlewareHandler):

    def __init__(self, application, request, **kwargs):
        super(BaseHandler, self).__init__(application, request, **kwargs)

        self.session = session.Session(application.session_manager, self)

    def get_argument(self, name, default=None, strip=True):
        return RequestHandler.get_argument(self, name, default, strip)

    def get_body_argument(self, name, default=None, strip=True):
        return RequestHandler.get_body_argument(self, name, default, strip)

    def get_template_namespace(self):
        namespace = dict(
            handler=self,
            request=self.request,
            current_user=self.current_user,
            locale=self.locale,
            translate=self.locale.translate,
            pgettext=self.locale.pgettext,
            static_url=self.static_url,
            xsrf_form_html=self.xsrf_form_html,
            reverse_url=self.reverse_url,
            session=self.session,
            strip_value=self.strip_value,
            escape_quote=self.escape_quote,
            string_display=self.string_display,
            datetime_format=self.datetime_format
        )
        namespace.update(self.ui)
        return namespace

    def get_current_user(self):
        user = self.session.get(KEY_SESSION_USER)
        return user

    def strip_value(self, value=''):
        return strip_tags(value)

    def escape_quote(self, value):
        if value.find('"') > -1:
            return value.replace('"', '\'')
        return value

    def string_display(self, value, default='-'):
        if isinstance(value, (bytes, str)):
            if value:
                return value
        return default

    def datetime_format(self, dt, dt_format='%Y-%m-%d %H:%M:%S', default='-'):
        if isinstance(dt, datetime.datetime):
            return datetime2str(dt, dt_format)
        if not dt:
            return default
        return dt


class NonXsrfBaseHandler(BaseHandler):

    def check_xsrf_cookie(self):
        pass


class RestBaseHandler(NonXsrfBaseHandler):

    def __init__(self, application, request, **kwargs):
        NonXsrfBaseHandler.__init__(self, application, request, **kwargs)
        self.access_token = self.get_access_token()
        self.client_timestamp = self.get_timestamp()
        self.signature = self.get_signature()
        self.i_args = self.get_i_args()

    def get_i_args(self):
        try:
            args = self.get_argument('i')
            if not args:
                args = self.get_body_argument('i')
            if args:
                return json.loads(base64decode(args).decode('utf-8'))
        except TypeError:
            pass
        except ValueError:
            pass

    def get_access_token(self):
        token = self.get_argument('token')
        if not token:
            token = self.get_body_argument('token')
        if token:
            val = RedisCache.get(md5(token))
            if val:
                return token
        return None

    def get_timestamp(self):
        timestamp = self.get_argument('timestamp')
        if not timestamp:
            timestamp = self.get_body_argument('timestamp')
        if timestamp:
            try:
                r_timestamp = int(timestamp)
                n_timestamp = datetime2timestamp(datetime.datetime.now())
                if n_timestamp - r_timestamp < 10:
                    return timestamp
            except (ValueError, JSONDecodeError):
                pass
        return None

    def get_signature(self):
        v_sign = self.get_argument('vsign')
        args = {
            'token': self.access_token,
            'timestamp': self.client_timestamp,
            'i': self.get_argument('i')
        }
        value = '&'.join(['='.join((key, str(args.get(key)))) for key in sorted(args.keys())])
        if md5(value).upper() == v_sign:
            return v_sign
        return None

    def get_argument(self, name, default=None, strip=True):
        result = NonXsrfBaseHandler.get_argument(self, name, default, strip)
        if result is None:
            try:
                args = json.loads(self.request.body.decode('utf-8'))
                if args:
                    result = args.get(name, default)
                    if strip and isinstance(result, (bytes, str)):
                        result = result.strip()
            except (ValueError, JSONDecodeError):
                pass
        return result

    def get_body_argument(self, name, default=None, strip=True):
        result = NonXsrfBaseHandler.get_body_argument(self, name, default, strip)
        if result is None:
            try:
                args = json.loads(self.request.body.decode('utf-8'))
                if args:
                    result = args.get(name, default)
                    if strip and isinstance(result, (bytes, str)):
                        result = result.strip()
            except (ValueError, JSONDecodeError):
                pass
        return result


class WechatBaseHandler(BaseHandler):

    def get_current_user(self):
        user = self.session.get(KEY_MEMBER_CODE)
        return user


class WechatAppletHandler(NonXsrfBaseHandler):

    def __init__(self, application, request, **kwargs):
        NonXsrfBaseHandler.__init__(self, application, request, **kwargs)
        # 初始化参数
        self.__parse_request_args()

    def get_i_argument(self, name, default=None):
        """
        获取i参数内容参数值
        :param name:
        :param default:
        :return:
        """
        return getattr(self, name, default)

    def __parse_request_args(self):
        """
        解析i参数
        :return:
        """
        i_args = self.__get_i_args()
        if i_args:
            for i_key, i_value in i_args.items():
                setattr(self, i_key, i_value)

        access_token = self.__get_access_token()
        if access_token:
            setattr(self, 'access_token', access_token)

        timestamp = self.__get_timestamp()
        if timestamp:
            setattr(self, 'timestamp', timestamp)

        signature = self.__get_signature()
        if signature:
            setattr(self, 'signature', signature)

    def __get_i_args(self):
        try:
            args = self.get_argument('i')
            if not args:
                args = self.get_body_argument('i')
            if args:
                return json.loads(base64decode(args).decode('utf-8'))
        except TypeError:
            pass
        except ValueError:
            pass
        return {}

    def __get_access_token(self):
        token = self.get_argument('token')
        if not token:
            token = self.get_body_argument('token')
        if token:
            val = RedisCache.get(md5(token))
            if val:
                return token
        return None

    def __get_timestamp(self):
        timestamp = self.get_argument('timestamp')
        if not timestamp:
            timestamp = self.get_body_argument('timestamp')
        if timestamp:
            try:
                r_timestamp = int(timestamp)
                n_timestamp = datetime2timestamp(datetime.datetime.now())
                if n_timestamp - r_timestamp < 10:
                    return timestamp
            except (ValueError, JSONDecodeError):
                pass
        return None

    def __get_signature(self):
        v_sign = self.get_argument('vsign')
        args = {
            'token': self.__get_access_token(),
            'timestamp': self.__get_timestamp(),
            'i': self.get_argument('i')
        }
        value = '&'.join(['='.join((key, str(args.get(key)))) for key in sorted(args.keys())])
        if md5(value).upper() == v_sign:
            return v_sign
        return None

    def get_argument(self, name, default=None, strip=True):
        result = NonXsrfBaseHandler.get_argument(self, name, default, strip)
        if result is None:
            try:
                args = json.loads(self.request.body.decode('utf-8'))
                if args:
                    result = args.get(name, default)
                    if strip and isinstance(result, (bytes, str)):
                        result = result.strip()
            except (ValueError, JSONDecodeError):
                pass
        return result

    def get_body_argument(self, name, default=None, strip=True):
        result = NonXsrfBaseHandler.get_body_argument(self, name, default, strip)
        if result is None:
            try:
                args = json.loads(self.request.body.decode('utf-8'))
                if args:
                    result = args.get(name, default)
                    if strip and isinstance(result, (bytes, str)):
                        result = result.strip()
            except (ValueError, JSONDecodeError):
                pass
        return result
