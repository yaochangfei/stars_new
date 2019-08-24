#!/usr/bin/python


import traceback
from datetime import datetime

from pymongo import ReadPreference

from actions.applet.utils import add_notice
from commons.common_utils import RedisCache
from db import RESULT_RACE_LOTTERY_WIN, RESULT_RACE_LOTTERY_LOSE, RESULT_RACE_LOTTERY_LOSE_LATE, TYPE_MSG_DRAW, \
    CATEGORY_REDPACKET_RULE_DIRECT, CATEGORY_REDPACKET_RULE_LOTTERY
from db.models import RedPacketBox, RedPacketRule, RedPacketBasicSetting, RedPacketConf, \
    RedPacketItemSetting
from enums import KEY_RACE_LOTTERY_RESULT
from logger import log_utils
from tasks import app

logger = log_utils.get_logging('task_lottery', 'task_lottery.log')


@app.task(bind=True, queue='lottery')
def start_lottery_queuing(self, member_cid, race_cid, rule: RedPacketRule, checkpoint_cid):
    """

    :param self:
    :param member_cid:
    :param race_cid:
    :param rule:
    :param checkpoint_cid:
    :return:
    """
    logger.info('START(%s): lottery queuing, race_cid=%s, checkpoint_cid=%s, member_id=%s ' % (
        self.request.id, race_cid, checkpoint_cid, member_cid))
    try:
        if not (member_cid and race_cid and rule):
            raise Exception('There is not member_cid or race_cid or rule')

        top_limit, fail_msg = None, None
        if rule.category == CATEGORY_REDPACKET_RULE_DIRECT:
            conf = RedPacketConf.sync_find_one({'rule_cid': rule.cid})
            top_limit = conf.top_limit
            fail_msg = conf.over_msg

        if rule.category == CATEGORY_REDPACKET_RULE_LOTTERY:
            conf = RedPacketBasicSetting.sync_find_one({'rule_cid': rule.cid})
            top_limit = conf.top_limit
            fail_msg = conf.fail_msg

        has_sent_count = RedPacketBox.sync_count({'rule_cid': rule.cid, 'draw_dt': {
            '$gte': datetime.now().replace(hour=0, minute=0, second=0),
            '$lte': datetime.now().replace(hour=23, minute=59, second=59)}, 'record_flag': 1},
                                                 read_preference=ReadPreference.PRIMARY)

        msg = None
        if has_sent_count >= top_limit:
            msg = conf.over_msg
            redpkt_box = RedPacketBox()
            result = RESULT_RACE_LOTTERY_LOSE_LATE
        else:
            redpkt_box = RedPacketBox.sync_find_one({'rule_cid': rule.cid, 'draw_dt': None, 'record_flag': 1})
            if not redpkt_box:
                msg = fail_msg
                redpkt_box = RedPacketBox()
                result = RESULT_RACE_LOTTERY_LOSE
            else:
                # 拿到了红包
                if not redpkt_box.award_msg:
                    item_setting = RedPacketItemSetting.sync_find_one({'rule_cid': rule.cid})
                    msg = item_setting.message
                    logger.error('item_msg: %s' % msg)

                if not redpkt_box.award_cid:
                    result = RESULT_RACE_LOTTERY_LOSE

        redpkt_box.race_cid = race_cid
        redpkt_box.rule_cid = rule.cid
        redpkt_box.checkpoint_cid = checkpoint_cid
        redpkt_box.member_cid = member_cid
        redpkt_box.draw_dt = datetime.now()

        if msg:
            redpkt_box.award_msg = msg
        redpkt_box.sync_save()

        win = bool(redpkt_box.award_cid)
        if win:
            result = RESULT_RACE_LOTTERY_WIN
            add_notice(member_cid, race_cid, checkpoint_cid, msg_type=TYPE_MSG_DRAW, redpkt_box=redpkt_box)

        RedisCache.hset(KEY_RACE_LOTTERY_RESULT.format(checkpoint_cid), member_cid, result)
        logger.info(' END (%s): lottery end , checkpoint_cid=%s, member_id=%s, result=%s ' % (
            self.request.id, checkpoint_cid, member_cid, result))
    except Exception:
        logger.error(traceback.format_exc())
        logger.error(
            'ERROR(%s): lottery error, checkpoint_cid=%s, member_id=%s, rule_cid=%s' % (
                self.request.id, checkpoint_cid, member_cid, rule.cid))
