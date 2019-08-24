#! /usr/bin/python


from db import CATEGORY_NOTICE_SYSTEM
from db.models import MemberNotice, Member
from pymongo import ReadPreference


def add_notice():
    # msg = """尊敬的用户您好，由于小程序商户到期重审，红包领取功能暂时无法使用，具体恢复时间另行通知。审核期间您可正常使用小程序所有功能，后台会照常发放红包，期间获得的所有红包将在审核通过后全部在“消息通知”里面直接领取。"""
    msg = """尊敬的用户您好，红包领取功能已经恢复正常，之前未领取的红包您可以前往“消息通知”里面直接领取。谢谢！"""
    cursor = Member.sync_find({}, read_preference=ReadPreference.PRIMARY).batch_size(2048)
    for index, member in enumerate(cursor):
        print('has notice', index)
        notice = MemberNotice()
        notice.member_cid = member.cid
        notice.category = CATEGORY_NOTICE_SYSTEM
        notice.content = msg
        notice.sync_save()


if __name__ == '__main__':
    add_notice()
