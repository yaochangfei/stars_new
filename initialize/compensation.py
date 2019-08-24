#! /usr/bin/python


import asyncio
from datetime import datetime

from pymongo import ReadPreference

from db import CATEGORY_NOTICE_SYSTEM, SOURCE_MEMBER_DIAMOND_ADMIN_UPDATE
from db.models import MemberNotice, Member, MemberDiamondDetail


async def do_genete():
    # _now = datetime.now()
    # bg_dt = _now.replace(year=2019, month=7, day=1, hour=12, minute=0, second=0)
    # ed_dt = _now.replace(year=2019, month=7, day=2, hour=14, minute=0, second=0)
    # member_list1 = await MemberGameHistory.distinct('member_cid', {'created_dt': {'$gt': bg_dt, '$lt': ed_dt}})
    # member_list2 = await MemberCheckPointHistory.distinct('member_cid', {'created_dt': {'$gt': bg_dt, '$lt': ed_dt}})
    # member_cids = set(member_list1).union(set(member_list2))

    _now = datetime.now()
    index = 0
    cursor = Member.find({'auth_address.province': '安徽省'}, read_preference=ReadPreference.PRIMARY).batch_size(128)
    while await cursor.fetch_next:
        try:
            member = cursor.next_object()

            award_value = 8000
            if member.cid == '0D8A69937D498A20BDFC05881E5C4DB3':
                award_value = 12000

            msg = '尊敬的用户您好，对于匹配超时而导致错误扣除钻石的问题，系统近期将返还%s钻石至您的账户，请注意查收。' % award_value
            member.diamond += award_value
            await member.save()

            notice = MemberNotice()
            notice.member_cid = member.cid
            notice.category = CATEGORY_NOTICE_SYSTEM
            notice.notice_datetime = _now
            notice.content = msg
            await notice.save()

            detail = MemberDiamondDetail()
            detail.member_cid = member.cid
            detail.diamond = award_value
            detail.source = SOURCE_MEMBER_DIAMOND_ADMIN_UPDATE
            detail.reward_datetime = _now
            detail.content = msg
            await detail.save()
            index += 1
            print('has done %s, cid: %s, diamond: %s' % (index, member.cid, award_value))
        except StopIteration:
            break


if __name__ == '__main__':
    pass
    task_list = [
        do_genete()
        # init_users(),
        # init_administrative_division(),
        # init_attribute(),
    ]
    loop = asyncio.get_event_loop()
    loop.run_until_complete(asyncio.wait(task_list))
    loop.close()
