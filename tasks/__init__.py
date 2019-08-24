# !/usr/bin/python
# -*- coding:utf-8 -*-

import sys

from celery import platforms

from settings import SITE_ROOT
from tasks import config
from tasks.utils import get_task_celery_instance

sys.path.insert(0, SITE_ROOT)

platforms.C_FORCE_ROOT = True

# 启用Celery实例
app = get_task_celery_instance(instance_name='celery_main_tasks', config_module=config)
