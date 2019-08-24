#! /usr/bin/python

"""补发六安未中奖红包

"""
from actions.applet.utils import add_notice
from db import TYPE_MSG_DRAW
from db.models import RedPacketBox


def do_resend():
    new_rule_cid = 'CC5C14D38A130733D94DACF109D337C0'
    has_money_box = RedPacketBox.sync_find_one({'rule_cid': new_rule_cid})
    print(has_money_box)
    cursor = RedPacketBox.sync_find({'rule_cid': "1F22A64622D5DC2A5D8660C809550F38", 'award_cid': None})

    index = 0
    while True:
        try:
            box: RedPacketBox = cursor.next()
            box.award_cid = has_money_box.award_cid
            box.award_amount = has_money_box.award_amount
            box.award_msg = has_money_box.award_msg
            box.draw_dt = None
            box.draw_status = None
            box.rule_cid = new_rule_cid
            box.needless['msg'] = 'resend'
            box.sync_save()

            index += 1
            print('has resend', index)
            add_notice(box.member_cid, box.race_cid, box.checkpoint_cid, msg_type=TYPE_MSG_DRAW, redpkt_box=box)

        except StopIteration:
            break


if __name__ == '__main__':
    do_resend()
