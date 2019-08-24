#! /usr/bin/python


from db import STATUS_REDPACKET_NOT_AWARDED
from db.models import RedPacketBox, Member


def query():
    amount = 0
    miss_members = set()
    with open('./rdp.txt', 'r') as f:
        for line in f.readlines():
            rid = line.replace('\n', '')
            box = RedPacketBox.sync_find_one({'redpkt_rid': rid})
            if not box:
                try:
                    race_cid, member_cid, redpacket_cid = line.split('-')
                    box = RedPacketBox.sync_get_by_cid(redpacket_cid)
                    if not box:
                        print('miss box', rid)
                        member = Member.sync_get_by_cid(member_cid)
                        if member:
                            miss_members.add(member.nick_name)
                        else:
                            print('miss member', member_cid)
                        continue
                except ValueError:
                    print('miss box', rid)
                    continue

            if box.draw_status == STATUS_REDPACKET_NOT_AWARDED:
                box.draw_status = 0
                box.sync_save()
                print('not draw', rid)
            else:
                print('success ', rid)
                amount += box.award_amount

    print(amount)
    print('-----')
    print(len(miss_members), miss_members)


if __name__ == '__main__':
    query()
