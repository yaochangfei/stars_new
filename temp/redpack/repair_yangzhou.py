#! /usr/bin/python

from db import STATUS_REDPACKET_AWARDED
from db.models import RedPacketAwardHistory, RedPacketBox, RedPacketItemSetting

rid_list = []
with open('miss.txt', 'r') as f:
    for line in f.readlines():
        rid_list.append(line.replace('\n', ''))

index = 0
for rid in rid_list:
    rdp = RedPacketAwardHistory.sync_find_one({'redpacket_rid': rid})
    if not rdp:
        print(index, rid)
        index += 1
    else:
        setting = RedPacketItemSetting.sync_get_by_cid(rdp.award_cid)

        box = RedPacketBox.sync_find_one({'redpkt_rid': rid})
        if '-' not in rid:
            print('--- skip ---', rid)
            continue

        if not box:
            box = RedPacketBox()
        box.race_cid = setting.race_cid
        box.rule_cid = setting.rule_cid
        box.award_cid = setting.cid
        box.award_msg = setting.message
        box.award_amount = setting.amount

        box.draw_status = STATUS_REDPACKET_AWARDED

        _, member_cid, _ = rid.split('-')
        box.member_cid = member_cid
        box.draw_dt = rdp.created_dt
        box.created_dt = rdp.created_dt
        box.updated_dt = rdp.updated_dt
        box.redpkt_rid = rid
        box.request_dt = rdp.request_dt
        box.request_status = rdp.request_status
        box.error_msg = rdp.error_msg
        box.sync_save()
        print('--- save ---', rid)
