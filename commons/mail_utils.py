# !/usr/bin/python
# -*- coding:utf-8 -*-
import os
import settings

from logger import log_utils
from tornado.template import Template

logger = log_utils.get_logging(name='mail_service', file_name='mail_service.log')

TEMPLATES_CACHE = {}


def render_template(template_name, **kwargs):
    """
    填充模板
    :param template_name: 模板名称
    :param kwargs: 填充参数
    :return: 填充后的结果
    """
    if template_name:
        global TEMPLATES_CACHE
        if template_name in TEMPLATES_CACHE.keys():
            return TEMPLATES_CACHE.get(template_name)
        else:
            path = os.path.join(settings.TEMPLATE_PATH, template_name)
            if os.path.exists(path):
                template = None
                try:
                    with open(path) as template:
                        t_content = template.read()
                        if t_content:
                            TEMPLATES_CACHE[template_name] = t_content
                finally:
                    if template:
                        template.close()
            else:
                raise FileNotFoundError("Template '%s' not found. " % template_name)

    t_content = TEMPLATES_CACHE.get(template_name)
    if t_content:
        if t_content:
            t = Template(t_content)
            return t.generate(**kwargs)
    return ''
