import random

from db.models import RedPacketEntry, RedPacketRule, RedPacketItemSetting, RedPacketConf, RedPacketBox


def get_award_position(people_count, award_num, current_posision=0):
    """计算奖品位置

    :param people_count:
    :param award_num:
    :return:
    """
    count = int(people_count / award_num)
    if count <= 1:
        # 必定中奖
        return list(range(1, award_num + 1))

    return [random.randint(current_posision + count * i, current_posision + count * (i + 1)) for i in
            range(1, award_num + 1)]


def get_item_position(red_item_list, red_item_count, expect_num):
    """
    所有奖品的位置分布
    :param red_item_list:
    :param red_item_count:
    :param expect_num
    :return:
    """
    #  所有奖品的位置
    red_item_position = []
    for red_item, count in zip(red_item_list, red_item_count):
        for i in range(count):
            red_item_position.append(red_item)
    for i in range(int(expect_num)):
        if len(red_item_position) < int(expect_num):
            red_item_position.append(None)
        else:
            break
    random.shuffle(red_item_position)
    return red_item_position


async def get_red_status_count(race_cid, red_item_list):
    """
    得到红包奖品的状态，比如说中奖个数和剩余奖品个数
    :param red_item_list:
    :return:
    """
    remain_prize_quantity_list = []
    win_prize_quantity_list = []
    for red_packet_item in red_item_list:
        win_prize_count = await RedPacketEntry.count(
            {'race_cid': race_cid, 'open_id': {'$ne': None}, 'award_cid': red_packet_item.cid})

        remain_prize_count = red_packet_item.count - win_prize_count
        remain_prize_quantity_list.append(remain_prize_count)
        win_prize_quantity_list.append(win_prize_count)
    return win_prize_quantity_list, remain_prize_quantity_list


async def can_delete_repkt_rule_setting(rule: RedPacketRule, check_lottery: bool = True) -> bool:
    """
    检查是否可以删除红包规则下的奖项设置

    :param rule:
    :param check_lottery:  检查抽奖
    :return:
    """

    if check_lottery:
        item_cids = await RedPacketItemSetting.distinct('cid', {'rule_cid': rule.cid})
        item_cids_conf = await RedPacketConf.find_one({'rule_cid': rule.cid})
        if item_cids_conf:
            item_cids.append(item_cids_conf.cid)
        if await RedPacketBox.count(
                {'award_cid': item_cids, 'member_cid': {'$ne': None}, 'record_flag': 1}) > 0:
            return False
    return True
