# !/usr/bin/python
# -*- coding:utf-8 -*-

import os
import re
import subprocess
import sys
import time

import settings
from caches.redis_utils import RedisCache
from enums import KEY_ALLOW_PROCESS_ACCURATE_STATISTICS, KEY_ALLOW_PROCESS_DOCKING_STATISTICS
from settings import SITE_ROOT

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


def get_server_pid(port):
    output = subprocess.getstatusoutput('ps aux|grep "python __main__.py"')
    if output:
        lines = output[1].split('\n')
        ps_dict = {}
        re_obj = re.compile(r' +(\d+).*-port=(\d+)$')
        for line in lines:
            result = re_obj.findall(line)
            if not result:
                continue
            pid, port1 = result[0]
            if pid:
                if ps_dict.get(port1) is None:
                    ps_dict[port1] = []
                ps_dict[port1].append(pid)
        return ps_dict.get(str(port))
    return None


def start_server(port):
    # 记录输出日志
    start_cmd = 'nohup python __main__.py -port=%s > /dev/null 2>&1 &' % port
    # 执行命令
    os.system(start_cmd)
    # 输出提示
    print('SERVER %s STARTED.' % port)
    time.sleep(0.2)


def stop_server(port):
    pid_list = get_server_pid(port)
    if pid_list:
        for pid in pid_list:
            if pid:
                os.system('kill -9 %s' % pid)
                print('SERVER %s STOPPED.' % port)
                time.sleep(0.2)
    else:
        print('PORT %s NO SERVER IN PROCESSING.' % port)


def get_task_pid():
    output = subprocess.getstatusoutput('ps aux|grep celery')
    lines = output[1].split('\n')
    re_obj = re.compile(r'[A-Za-z]+\s{2,}\d{2,5}')
    pid_list = []
    for line in lines:
        if line.find('worker -A') > 0 or line.find('beat -A') > 0:
            result = re_obj.findall(line)
            if not result:
                continue
            result = re.compile(r'\d{4,}').findall(result[0])
            if result:
                result = result[0]
                if result:
                    pid_list.append(result)
    pid_list.sort()
    return pid_list


def path_2_module(path=''):
    if path:
        module = path.replace('\\', '/').replace(SITE_ROOT.replace('\\', '/'), '')
        if module.startswith('/'):
            module = module[1:]
        module = module.replace('/', '.').replace('.py', '').strip()
        if module:
            return module
    return None


def start_tasks(log_std_2_file=False):
    if settings.TASKS_FUNC_MODULE_CFG_LIST:
        worker_cmd = 'nohup celery worker -A %s -c %s -l %s --pidfile %s > %s 2>&1 &'
        beat_cmd = 'nohup celery beat -A %s -s %s -l %s --pidfile %s > %s 2>&1 &'

        log_file = '/dev/null'
        if log_std_2_file:
            log_file = os.path.join(settings.TEMP_PATH, 'tasks_worker_std_out.log')

        worker_pid = os.path.join(settings.TEMP_PATH, 'tasks_worker.pid')
        cmd = worker_cmd % ('tasks', settings.WORKER_CONCURRENCY, settings.LOG_LEVEL, worker_pid, log_file)
        # 启动Worker
        os.system(cmd)
        if settings.SCHEDULE_IN:
            if log_std_2_file:
                log_file = os.path.join(settings.TEMP_PATH, 'tasks_beat_std_out.log')
            worker_pid = os.path.join(settings.TEMP_PATH, 'tasks_beat.pid')
            cmd = beat_cmd % ('tasks', os.path.join(settings.TEMP_PATH, 'schedule_beat'), settings.LOG_LEVEL,
                              worker_pid, log_file)
            # 启动Beat
            os.system(cmd)
            print('TASK STARTED，WORKER_NUM=%s, PERIODIC=ON.' % settings.WORKER_CONCURRENCY)
            time.sleep(1)
        else:
            print('TASK STARTED, WORKER_NUM=%s.' % settings.WORKER_CONCURRENCY)
            time.sleep(1)

        # 清除队列限制
        RedisCache.set(KEY_ALLOW_PROCESS_ACCURATE_STATISTICS, 0)
        RedisCache.set(KEY_ALLOW_PROCESS_DOCKING_STATISTICS, 0)
    else:
        print('NO TASK SET.')


def stop_tasks():
    pid_list = get_task_pid()
    for pid in pid_list:
        if pid:
            stop_cmd = 'kill -9 %s' % pid
            os.system(stop_cmd)
            print('TASK[PID:%s] STOPPED.' % pid)
            time.sleep(1)
