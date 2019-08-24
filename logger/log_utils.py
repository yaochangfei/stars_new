# !/usr/bin/python
# -*- coding:utf-8 -*-

import logging
import os
import sys

from logging.handlers import TimedRotatingFileHandler

import settings as ss

LOGGING_MAPPING = {}

DEFAULT_DATE_FORMAT = '%y%m%d %H:%M:%S'
DEFAULT_FORMAT = '[%(levelname)1.1s %(asctime)s %(module)s:%(lineno)d] %(message)s'


def get_logging(name=None, file_name=None) -> logging.Logger:
    name = str(name) if name else 'default'
    file_name = str(file_name) if file_name else ss.LOG_NAME

    global LOGGING_MAPPING
    log_key = ('%s_%s' % (name, file_name)).replace('.', '_')
    if log_key not in LOGGING_MAPPING.keys():
        _generate_logger(name, file_name)
    return LOGGING_MAPPING.get(log_key)


def _generate_logger(name=None, file_name=None):
    global LOGGING_MAPPING

    logger = logging.getLogger(name if name else 'default')

    log_file = os.path.join(ss.LOG_PATH, file_name) if file_name else os.path.join(ss.LOG_PATH, ss.LOG_NAME)

    channel_handler = TimedRotatingFileHandler(
        filename=log_file, when='MIDNIGHT', interval=1, backupCount=14)
    channel_handler.setFormatter(
        logging.Formatter(DEFAULT_FORMAT, datefmt=DEFAULT_DATE_FORMAT))
    logger.addHandler(channel_handler)

    if ss.LOG_STDERR:
        console_channel = logging.StreamHandler(sys.stderr)
        console_channel.setFormatter(
            logging.Formatter(DEFAULT_FORMAT))
        logger.addHandler(console_channel)

    # 设置日志等级
    logger.setLevel(ss.LOG_LEVEL)

    log_key = ('%s_%s' % (name, file_name)).replace('.', '_')
    LOGGING_MAPPING[log_key] = logger
