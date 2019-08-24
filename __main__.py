# !/usr/bin/python
# -*- coding:utf-8 -*-
import logging
import os
import random

import sys
from logging.handlers import TimedRotatingFileHandler

from tornado import options, httpclient
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
from tornado.netutil import bind_sockets
from tornado.options import define
from tornado.process import fork_processes

import settings
from web.base import IBApplication

define('port', default=settings.SERVER_PORT, type=int, help='Run server on given port.')
define('request_handler_middleware', default=settings.REQUEST_HANDLER_MIDDLEWARE_LIST, type=list,
       help='Middleware for request handler.')

# 解决HTTPS请求要求证书的问题
if settings.SERVER_PORT == 443:
    httpclient.AsyncHTTPClient.configure("tornado.curl_httpclient.CurlAsyncHTTPClient")


def do_prepare():
    # 初始化日志目录
    if not os.path.exists(settings.LOG_PATH):
        os.makedirs(settings.LOG_PATH)

    # 初始化附件目录
    if not os.path.exists(settings.UPLOAD_FILES_PATH):
        os.makedirs(settings.UPLOAD_FILES_PATH)


def do_bind_logger_config(task_id=None):
    """
    绑定日志配置
    :param task_id:
    :return:
    """
    if task_id is None:
        task_id = random.randint(1024, 4096)
    log_format = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s'
    log_date_format = '%y%m%d %H:%M:%S'

    logger = logging.getLogger('tornado.access')
    logger.setLevel(settings.LOG_LEVEL)

    # 输出到文件同时按日期分割
    log_file = os.path.join(
        settings.LOG_PATH, settings.LOG_NAME_ACCESS.replace('.', '%s.%s.' % (get_server_port(), task_id)))
    timed_channel = TimedRotatingFileHandler(filename=log_file, when='MIDNIGHT', backupCount=30)
    timed_channel.setFormatter(logging.Formatter(log_format, datefmt=log_date_format))
    logger.addHandler(timed_channel)
    logger.info('Access logs to %s ' % log_file)

    if settings.LOG_STDERR:
        # 输出到标准输出流
        stream_channel = logging.StreamHandler()
        stream_channel.setFormatter(logging.Formatter(log_format, datefmt=log_date_format))
        logger.addHandler(stream_channel)
    return logger


def get_server_port():
    """
    获取服务端口
    :return:
    """
    args = sys.argv
    for i, v in enumerate(args):
        remain = ''
        if v.startswith("--"):
            remain = v[2:]
        elif v.startswith("-"):
            remain = v[1:]
        if remain:
            name, equals, value = remain.partition("=")
            if name.upper() == 'PORT':
                return int(value)
    return options.options.port


def do_start():
    #  准备工作，系统准备工作放到这个方法里
    do_prepare()

    # 解析参数
    options.parse_command_line()

    # 服务器配置
    app_opt = dict(
        session_secret=settings.SESSION_SECRET_KEY,
        session_timeout=settings.SESSION_TIMEOUT,
        cookie_secret=settings.COOKIE_SECRET_KEY,
        xsrf_cookies=settings.XSRF_COOKIES,
        xsrf_cookie_version=settings.XSRF_COOKIE_VERSION,
        autoescape=settings.AUTO_ESCAPE,
        compress_response=settings.COMPRESS_RESPONSE,
        template_path=settings.TEMPLATE_PATH,
        static_hash_cache=settings.STATIC_HASH_CACHE,
        static_path=settings.STATIC_PATH,
        static_url_prefix=settings.STATIC_URL_PREFIX,
        autoreload=settings.AUTO_RELOAD
    )

    # 创建 & 启动服务
    application = IBApplication(handlers=[], **app_opt)
    http_server, task_id = None, ''
    if settings.OS.upper() == 'WINDOWS':
        logger = do_bind_logger_config()
        application.listen(options.options.port)
    else:
        # 绑定监听端口
        sockets = bind_sockets(options.options.port)
        # Fork服务，参数为服务数量，必须整型且不能为负数，0：依据CPU核心数量启动服务数量
        task_id = fork_processes(settings.NUM_PROCESSES)
        # 绑定日志配置
        logger = do_bind_logger_config(task_id)

        http_server = HTTPServer(application, xheaders=True)
        # 添加监听
        http_server.add_sockets(sockets)
    # 注册请求处理句柄
    application.register_handlers()

    logger.info('Started web server(%s) on %s://%s:%s' % (
        task_id, settings.SERVER_PROTOCOL, settings.SERVER_HOST, options.options.port))

    IOLoop.current().start()

    if http_server:
        http_server.stop()
    IOLoop.current().stop()


if __name__ == '__main__':
    do_start()
