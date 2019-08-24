from random import shuffle, random

from db import CATEGORY_REDPACKET_CONST, CATEGORY_REDPACKET_RANDOM
from db.models import RedPacketConf, RedPacketBox
from motorengine.stages import MatchStage
from motorengine.stages.group_stage import GroupStage
from pymongo import ReadPreference


async def generate_awards_by_item_settings(basic_setting, settings):
    """

    :param basic_setting:
    :param settings:
    :return:
    """
    if not (basic_setting and settings):
        raise Exception('no basic_setting or settings')

    # 删除还未发出的红包
    await RedPacketBox.delete_many({'rule_cid': basic_setting.rule_cid, 'member_cid': None})
    box_list = await RedPacketBox.aggregate([
        MatchStage({'rule_cid': basic_setting.rule_cid, 'award_cid': {'$ne': None}}),
        GroupStage('award_cid', sum={'$sum': 1})
    ], read_preference=ReadPreference.PRIMARY).to_list(None)

    # 红包的发放情况
    get_situ = {box.id: box.sum for box in box_list}

    award_list = list()
    for config in settings:
        for _ in range(config.quantity - get_situ.get(config.cid, 0)):
            box = RedPacketBox()
            box.race_cid = basic_setting.race_cid
            box.rule_cid = basic_setting.rule_cid
            box.award_cid = config.cid
            box.award_msg = config.message
            box.award_amount = config.amount
            award_list.append(box)

    has_sent_count = sum(get_situ.values())
    while len(award_list) < basic_setting.expect_num - has_sent_count:
        box = RedPacketBox()
        box.race_cid = basic_setting.race_cid
        box.rule_cid = basic_setting.rule_cid
        box.award_msg = basic_setting.fail_msg
        award_list.append(box)

    shuffle(award_list)
    if award_list:
        for award in award_list:
            await award.save()


async def generate_awards_by_config(config: RedPacketConf):
    """

    :param config:
    :return:
    """
    if not config or config.quantity == 0:
        raise Exception('parameter error')

    await RedPacketBox.delete_many({'rule_cid': config.rule_cid})
    award_list = list()

    random_list = []
    if config.category == CATEGORY_REDPACKET_RANDOM:
        random_list = generate_random_list(config.quantity, config.total_amount)

    index = 0
    while index < config.quantity:
        index += 1
        box = RedPacketBox()
        box.race_cid = config.race_cid
        box.rule_cid = config.rule_cid
        box.award_cid = config.cid
        box.award_msg = config.msg
        if config.category == CATEGORY_REDPACKET_CONST:
            box.award_amount = config.total_amount / config.quantity

        if config.category == CATEGORY_REDPACKET_RANDOM:
            current_sum_amount = sum([award.award_amount for award in award_list])
            if current_sum_amount < config.total_amount:
                box.award_amount = random_list[len(award_list)]

        award_list.append(box)
        if len(award_list) > 2000:
            await RedPacketBox.insert_many(award_list)
            award_list = []

    if award_list:
        await RedPacketBox.insert_many(award_list)


def generate_random_list(quantity: int = 0, total_amount: float = 0.0):
    """

    :param quantity:
    :param total_amount:
    :return:
    """
    random_list = list()
    avg_value = int(total_amount / quantity)
    float_range = 1

    if quantity % 2 == 0:
        for _ in range(1, quantity, 2):
            random_list += random_up_low(avg_value, float_range)

    else:
        for _ in range(1, quantity - 1, 2):
            random_list += random_up_low(avg_value, float_range)

        current_sum = sum(random_list)
        assert current_sum <= total_amount

        random_list.append(total_amount - current_sum)

    shuffle(random_list)
    return random_list


def random_up_low(avg_value, float_range):
    """
    随机获得浮动的上下值

    :param avg_value:
    :param float_range:
    :return:
    """
    bias = round(random() * float_range, 2)

    low = round(avg_value - bias, 2)
    up = round(avg_value + bias, 2)
    while low < 1:
        if avg_value - float_range <= 0:
            raise ValueError('illegal value: ave_value: %s, float_range: %s' % (avg_value, float_range))
        low = round(avg_value - bias, 2)
        up = round(avg_value + bias, 2)

    return [low, up]
