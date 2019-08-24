# !/usr/bin/python
# -*- coding:utf-8 -*-
import sys
import time

from escript import start_server, stop_server, start_tasks, stop_tasks

if __name__ == '__main__':
    activity = sys.argv[1]
    action = sys.argv[2]
    try:
        if activity == 'server':
            port_from = int(sys.argv[3])
            process_number = int(sys.argv[4])
            if action == 'start':
                for port in range(port_from, port_from + process_number):
                    start_server(port)
            elif action == 'stop':
                for port in range(port_from, port_from + process_number):
                    stop_server(port)
            elif action == 'restart':
                for port in range(port_from, port_from + process_number):
                    stop_server(port)
                print('Please wait a moment...')
                time.sleep(1)
                for port in range(port_from, port_from + process_number):
                    start_server(port)
    except RuntimeError:
        print('Usage: main.py <task> <action> <port_from> <process_number>')

    try:
        if activity == 'tasks':
            if action == 'start':
                start_tasks(True)
            elif action == 'stop':
                stop_tasks()
            elif action == 'restart':
                stop_tasks()
                print('Please wait a moment...')
                time.sleep(1)
                start_tasks(True)
    except RuntimeError:
        print('Usage: main.py <task> <action>')

    sys.exit(1)
