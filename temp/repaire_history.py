#! /usr/bin/python


import asyncio
from asyncio import sleep
from datetime import datetime

from db.models import MemberGameHistory
from pymongo import ReadPreference
from pymongo.errors import CursorNotFound
from tasks.instances.task_report_dashboard_statistics import start_dashboard_report_statistics


async def do_repair():
    s_dt = datetime.now().replace(year=2019, month=7, day=3, hour=9, minute=58, second=59, microsecond=858)
    e_dt = datetime.now().replace(year=2019, month=7, day=10, hour=16, minute=0, second=0, microsecond=0)

    index = 0
    cursor = MemberGameHistory.find({'created_dt': {"$gte": s_dt, "$lte": e_dt}},
                                    read_preference=ReadPreference.PRIMARY).skip(index).batch_size(256)
    while await cursor.fetch_next:
        try:
            history = cursor.next_object()
            await start_dashboard_report_statistics(history)
            index += 1
            print('has repair', index, history.cid)
            await sleep(0.5)
        except StopIteration:
            break
        except CursorNotFound:
            cursor = MemberGameHistory.find({'created_dt': {"$gte": s_dt, "$lte": e_dt}},
                                            read_preference=ReadPreference.PRIMARY).skip(index).batch_size(256)


task_list = [
    do_repair(),
]
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait(task_list))
loop.close()
