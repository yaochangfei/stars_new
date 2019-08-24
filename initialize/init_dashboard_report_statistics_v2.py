# !/usr/bin/python


import asyncio
import datetime
import subprocess

from caches.redis_utils import RedisCache
from db.models import MemberGameHistory, MemberCheckPointHistory, Member
from enums import KEY_PREFIX_TASK_REPORT_DATA_STATISTICS
from pymongo import ReadPreference
from tasks.instances.task_report_dashboard_statistics import start_dashboard_report_statistics_without_delay


async def get_fight_history_models():
    begin_dt = datetime.datetime.now().replace(year=2019, month=5, day=16, hour=0, minute=0, second=0, microsecond=0)
    end_dt = datetime.datetime.now().replace(year=2019, month=6, day=14, hour=0, minute=0, second=0, microsecond=0)
    # 获取对战历史
    return MemberGameHistory.find(
        dict(record_flag=1, created_dt={"$gte": begin_dt, "$lte": end_dt}),
        read_preference=ReadPreference.PRIMARY).batch_size(32)


async def get_race_history_models():
    # 获取竞赛历史
    return MemberCheckPointHistory.find(
        dict(record_flag=1), read_preference=ReadPreference.PRIMARY).batch_size(32)


async def deal_with_history():
    """
    遍历历史记录，生成报表数据
    :return:
    """
    fight_history_list = await get_fight_history_models()
    count = 1
    while await fight_history_list.fetch_next:
        fight_history = fight_history_list.next_object()
        if fight_history:
            member = await Member.get_by_cid(fight_history.member_cid)
            if member:
                RedisCache.delete('%s_%s%s' % (KEY_PREFIX_TASK_REPORT_DATA_STATISTICS, member.cid, fight_history.cid))

                # while True:
                #     mem = get_mem_use_percent()
                #     if mem <= 0.7:
                #         print('--- current_mem: %s ---' % mem)
                #         break
                #     else:
                #         print('--- sleeping ---')
                #         await asyncio.sleep(40)

                await start_dashboard_report_statistics_without_delay(fight_history, member)
                print(count, member.nick_name, fight_history.fight_datetime)
                # if count % 2000 == 0:
                #     print('sleeping 45s...')
                #     time.sleep(45)
                count += 1

    # race_history_list = await get_race_history_models()
    # while await race_history_list.fetch_next:
    #     race_history = race_history_list.next_object()
    #     if race_history:
    #         member = await Member.get_by_cid(race_history.member_cid)
    #         if member:
    #             RedisCache.delete('%s_%s%s' % (KEY_PREFIX_TASK_REPORT_DATA_STATISTICS, member.cid, race_history.cid))
    #             await start_dashboard_report_statistics(race_history, member)
    #             print(count, member.nick_name, race_history.fight_datetime)
    #             if count % 2000 == 0:
    #                 print('sleeping 45s...')
    #                 time.sleep(45)
    #             count += 1


def get_mem_use_percent():
    """
    获取环境当前内存占用
    :return:
    """
    total_cmd = "free -m | awk '{print $2}'| sed -n '2p'"
    used_cmd = "free -m | awk '{print $3}'| sed -n '2p'"
    _, total = subprocess.getstatusoutput(total_cmd)
    _, used = subprocess.getstatusoutput(used_cmd)

    return int(used) / int(total)


task_list = [
    deal_with_history()
]
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait(task_list))
loop.close()
