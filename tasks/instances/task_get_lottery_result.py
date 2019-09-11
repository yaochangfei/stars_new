import json
import time
import traceback

import requests
from pymongo import ReadPreference

from actions.applet.utils import deal_param
from db import STATUS_REDPACKET_AWARDED, STATUS_READPACKET_ISSUE_SUCCESS, CATEGORY_NOTICE_AWARD, STATUS_NOTICE_UNREAD, \
    STATUS_NOTICE_READ, STATUS_REDPACKET_AWARD_FAILED, STATUS_READPACKET_ISSUE_FAIL
from db.models import RedPacketBox, Race, Member, MemberNotice
from logger import log_utils
from settings import REDPACKET_PLATFORM_QUERY_RESULT_URL, REDPACKET_PLATFORM_HOST
from tasks import app

logger = log_utils.get_logging('lottery_result')


@app.task(bind=True, queue='lottery_result')
def get_lottery_result(self, member: Member, reward_cid, rid):
    """
    获取到小程序抽奖结果
    :param self:
    :param member:
    :param reward_cid:
    :param rid:
    :return:
    """
    logger.info('START(%s): lottery result query, member_cid=%s, reward_cid=%s, rid=%s ' % (
        self.request.id, member.cid, reward_cid, rid))
    try:
        redpacket = RedPacketBox.sync_find_one({'member_cid': member.cid, 'cid': reward_cid, 'record_flag': 1},
                                               read_preference=ReadPreference.PRIMARY)

        race = Race.sync_get_by_cid(redpacket.race_cid)
        time_start = time.time()
        while time.time() - time_start < 30:
            time.sleep(1)

            json_data = json.dumps(
                deal_param(REDPACKET_PLATFORM_QUERY_RESULT_URL, redpkt_account=race.redpkt_account, rid=rid))
            res = requests.get(REDPACKET_PLATFORM_HOST + REDPACKET_PLATFORM_QUERY_RESULT_URL, data=json_data)
            res = res.json()
            status = res.get('data')[0].get('status')

            if status == 2:
                logger.warning('[RedPacket Drawing] the redpacket info: '
                               'member_cid: %s, checkpoint_cid: %s.' % (member.cid, redpacket.checkpoint_cid))

            if status == 3:
                redpacket.draw_status = STATUS_REDPACKET_AWARDED
                redpacket.issue_status = STATUS_READPACKET_ISSUE_SUCCESS

                redpacket.sync_save()

                notice_list = MemberNotice.sync_find(
                    {'member_cid': member.cid, 'category': CATEGORY_NOTICE_AWARD, 'status': STATUS_NOTICE_UNREAD,
                     'checkpoint_cid': redpacket.checkpoint_cid, 'record_flag': 1}).to_list(None)

                for notice in notice_list:
                    notice.status = STATUS_NOTICE_READ
                    notice.sync_save()
                logger.info(
                    '[RedPacket Drew] the redpacket info: member_cid: %s, checkpoint_cid: %s.' % (member.cid,
                                                                                                  redpacket.checkpoint_cid))
                break

            if status == 5:
                redpacket.status = STATUS_REDPACKET_AWARD_FAILED
                redpacket.issue_status = STATUS_READPACKET_ISSUE_FAIL
                redpacket.sync_save()
                break

            if status == 6:
                logger.warning(
                    '[RedPacket Waiting] the redpacket info: member_cid: %s, checkpoint_cid: %s.' % (member.cid,
                                                                                                     redpacket.checkpoint_cid))

            if status == 8:
                pass

    except Exception:
        logger.error(str(res.content))
        logger.error(traceback.format_exc())
    logger.info(' END (%s): lottery result query, member_cid=%s, reward_cid=%s, rid=%s ' % (
        self.request.id, member.cid, reward_cid, rid))
