# !/usr/bin/python
# -*- coding:utf-8 -*-


import settings

from tasks.utils import get_tasks_imports_and_queues

# 禁用UTC时间
enable_utc = False

# 任务中介设置
broker_url = 'redis://%s:%s/%s' % (settings.REDIS_TASK_HOST, settings.REDIS_TASK_PORT, settings.REDIS_TASK_DB)
broker_connection_timeout = 5  # 连接超时时间(单位：S)
broker_connection_retry = True  # 超时重试
broker_connection_max_retries = 5  # 超时重试次数
broker_pool_limit = 64  # 连接池数量

# 任务序列化方式
task_serializer = 'pickle'
accept_content = ['pickle']

# 任务设置
worker_concurrency = settings.WORKER_CONCURRENCY
task_time_limit = 30 * 60  # 超时时间
task_track_started = True  # 报告任务开始状态
worker_redirect_stdouts = True  # 重定向到标准输出流
worker_redirect_stdouts_level = settings.LOG_LEVEL  # 标准输出流日志水平(DEBUG|INFO|WARNING|ERROR|CRITICAL)

# 结果缓存
# result_backend = 'redis://%s:%s/%s' % (settings.REDIS_TASK_HOST, settings.REDIS_TASK_PORT, 3)
# result_expires = 2 * 60 * 60  # 结果超时时间

imports, task_queues = get_tasks_imports_and_queues()
