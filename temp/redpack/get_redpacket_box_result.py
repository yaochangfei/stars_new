#! /usr/bin/python


import json

import requests
from actions.applet.utils import deal_param, generate_rid
from db import STATUS_REDPACKET_AWARDED, STATUS_READPACKET_ISSUE_SUCCESS, CATEGORY_NOTICE_AWARD, STATUS_NOTICE_UNREAD, \
    STATUS_NOTICE_READ, STATUS_REDPACKET_AWARD_FAILED, STATUS_READPACKET_ISSUE_FAIL
from db.models import RedPacketBox, Race, MemberNotice
from logger import log_utils
from settings import REDPACKET_PLATFORM_QUERY_RESULT_URL, REDPACKET_PLATFORM_HOST

logger = log_utils.get_logging('daily_lottery_result_query', 'daily_lottery_result_query.log')


def do_query(race_cid):
    cursor = RedPacketBox.sync_find(
        {'member_cid': {'$ne': None}, 'award_cid': {'$ne': None}, 'draw_status': 1, 'race_cid': race_cid}).batch_size(
        128)

    index = 0
    while True:
        try:
            box: RedPacketBox = cursor.next()
            race = Race.sync_get_by_cid(box.race_cid)
            rid = generate_rid(box.race_cid, box.member_cid, box.cid)
            json_data = json.dumps(
                deal_param(REDPACKET_PLATFORM_QUERY_RESULT_URL, redpkt_account=race.redpkt_account, rid=rid))
            res = requests.get(REDPACKET_PLATFORM_HOST + REDPACKET_PLATFORM_QUERY_RESULT_URL, data=json_data)
            res = res.json()

            if res.get('data'):
                status = res.get('data')[0].get('status')
            else:
                print('member has not click pick_url')
                continue

            if status == 2:
                print('[RedPacket Drawing] the redpacket info: '
                            'member_cid: %s, checkpoint_cid: %s.' % (box.member_cid, box.checkpoint_cid))

            if status == 3:
                box.draw_status = STATUS_REDPACKET_AWARDED
                box.issue_status = STATUS_READPACKET_ISSUE_SUCCESS

                box.sync_save()

                notice_list = MemberNotice.sync_find(
                    {'member_cid': box.member_cid, 'category': CATEGORY_NOTICE_AWARD, 'status': STATUS_NOTICE_UNREAD,
                     'checkpoint_cid': box.checkpoint_cid, 'record_flag': 1}).to_list(None)

                for notice in notice_list:
                    notice.status = STATUS_NOTICE_READ
                    notice.sync_save()
                print(
                    '[RedPacket Drew] the redpacket info: member_cid: %s, checkpoint_cid: %s.' % (box.member_cid,
                                                                                                  box.checkpoint_cid))
                break

            if status == 5:
                box.status = STATUS_REDPACKET_AWARD_FAILED
                box.issue_status = STATUS_READPACKET_ISSUE_FAIL
                box.sync_save()
                break

            if status == 6:
                logger.warning(
                    '[RedPacket Waiting] the redpacket info: member_cid: %s, checkpoint_cid: %s.' % (box.member_cid,
                                                                                                     box.checkpoint_cid))

            if status == 8:
                pass

            index += 1
            print('has query', index)

        except StopIteration:
            break


if __name__ == '__main__':
    _cid = '3040737C97F7C7669B04BC39A660065D'
    do_query(_cid)
