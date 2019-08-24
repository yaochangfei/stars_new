#!/usr/bin/python


import copy
import hashlib
import json
import uuid
from datetime import datetime

from bson import ObjectId

from commons import menu_utils
from pymongo import ReadPreference

from actions.backoffice.race.redpkt_rule.utils import generate_awards_by_item_settings, generate_awards_by_config
from caches.redis_utils import RedisCache
from db.models import RaceSubjectRefer, RaceGameCheckPoint, RaceSubjectChoiceRules, RaceSubjectBanks, RedPacketRule, \
    Company, RedPacketItemSetting, RedPacketConf, RedPacketBasicSetting, Race
from enums import KEY_CACHE_RACE_COPY_MAP, KEY_SESSION_USER_MENU


def get_new_cid():
    return hashlib.md5(str(uuid.uuid1()).encode('utf-8')).hexdigest().upper()


async def do_copy_subject_refer(race_cid, new_race_cid, user_cid):
    """
    复制维度
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """
    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')

    subject_map = {}
    old_subject_cursor = RaceSubjectRefer.find({'race_cid': race_cid},
                                               read_preference=ReadPreference.PRIMARY).batch_size(32)

    new_subject_list = []
    while await old_subject_cursor.fetch_next:
        subject = old_subject_cursor.next_object()

        new_subject = copy.deepcopy(subject)
        new_subject.cid = get_new_cid()
        new_subject.race_cid = new_race_cid
        new_subject.updated_id = user_cid
        subject_map[subject.cid] = new_subject.cid

        new_subject_list.append(new_subject)

    RedisCache.set(KEY_CACHE_RACE_COPY_MAP + race_cid + '_subject_copy', json.dumps(subject_map))
    await RaceSubjectRefer.insert_many(new_subject_list)


async def do_copy_checkpoint(race_cid, new_race_cid, user_cid):
    """
    复制关卡
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """

    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')

    old_checkpoint_cursor = RaceGameCheckPoint.find({'race_cid': race_cid},
                                                    read_preference=ReadPreference.PRIMARY).batch_size(32)

    rule_map = json.loads(RedisCache.get(KEY_CACHE_RACE_COPY_MAP + race_cid + '_rule_copy'))
    red_packet_map = json.loads(RedisCache.get(KEY_CACHE_RACE_COPY_MAP + race_cid + '_red_packet_rule_copy'))
    new_checkpoint_list = []
    checkpoint_map = {}
    while await old_checkpoint_cursor.fetch_next:
        checkpoint = old_checkpoint_cursor.next_object()
        new_checkpoint = copy.deepcopy(checkpoint)
        new_checkpoint.cid = get_new_cid()
        new_checkpoint.race_cid = new_race_cid
        new_checkpoint.rule_cid = rule_map[checkpoint.rule_cid]
        new_checkpoint.redpkt_rule_cid = red_packet_map[checkpoint.redpkt_rule_cid] if checkpoint.redpkt_rule_cid else ''
        new_checkpoint.updated_id = user_cid
        checkpoint_map[checkpoint.cid] = new_checkpoint.cid
        new_checkpoint_list.append(new_checkpoint)
    RedisCache.set(KEY_CACHE_RACE_COPY_MAP + race_cid + '_checkpoint_copy', json.dumps(checkpoint_map))
    await RaceGameCheckPoint.insert_many(new_checkpoint_list)


async def do_copy_choice_rule(race_cid, new_race_cid, user_cid):
    """
    复制抽题规则
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """
    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')

    old_rule_cursor = RaceSubjectChoiceRules.find({'race_cid': race_cid},
                                                  read_preference=ReadPreference.PRIMARY).batch_size(32)

    rule_map = {}
    new_rule_list = []
    while await old_rule_cursor.fetch_next:
        rule = old_rule_cursor.next_object()

        new_rule = copy.deepcopy(rule)
        new_rule.cid = get_new_cid()
        new_rule.race_cid = new_race_cid
        new_rule.updated_id = user_cid

        rule_map[rule.cid] = new_rule.cid

        new_rule_list.append(new_rule)

    await RaceSubjectChoiceRules.insert_many(new_rule_list)
    RedisCache.set(KEY_CACHE_RACE_COPY_MAP + race_cid + '_rule_copy', json.dumps(rule_map))


async def do_copy_subject_bank(race_cid, new_race_cid, user_cid):
    """
    复制题库
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """

    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')

    old_bank_cursor = RaceSubjectBanks.find({'race_cid': race_cid}, read_preference=ReadPreference.PRIMARY).batch_size(
        32)
    subject_map = json.loads(RedisCache.get(KEY_CACHE_RACE_COPY_MAP + race_cid + '_subject_copy'))
    rule_map = json.loads(RedisCache.get(KEY_CACHE_RACE_COPY_MAP + race_cid + '_rule_copy'))

    new_bank_list = []
    while await old_bank_cursor.fetch_next:
        old_bank = old_bank_cursor.next_object()

        new_bank = copy.deepcopy(old_bank)
        new_bank.cid = get_new_cid()
        new_bank.race_cid = new_race_cid
        new_bank.choice_dt = datetime.now()
        new_bank.rule_cid = rule_map[old_bank.rule_cid]
        new_bank.refer_subject_cid_list = [subject_map[cid] for cid in old_bank.refer_subject_cid_list]
        new_bank.updated_id = user_cid

        new_bank_list.append(new_bank)

    await RaceSubjectBanks.insert_many(new_bank_list)


async def do_copy_red_packet_rule(race_cid, new_race_cid, user_cid):
    """
    复制红包规则
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """
    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')
    old_redpkt_rule_cursor = RedPacketRule.find({'race_cid': race_cid},
                                                read_preference=ReadPreference.PRIMARY).batch_size(32)
    award_map = {}
    red_rule_map = {}
    new_red_packet_list = []
    new_item_conf_list = []
    new_item_setting_list = []
    while await old_redpkt_rule_cursor.fetch_next:
        red_packet = old_redpkt_rule_cursor.next_object()
        new_red_packet = copy.deepcopy(red_packet)
        new_red_packet.cid = get_new_cid()
        new_red_packet.race_cid = new_race_cid
        new_red_packet.updated_id = user_cid
        red_rule_map[red_packet.cid] = new_red_packet.cid
        #  复制红包规则里面的红包配置
        new_item_conf = ''
        if red_packet.category == 1:
            red_item_conf = await RedPacketConf.find_one({'rule_cid': red_packet.cid, 'record_flag': 1})
            if red_item_conf:
                new_item_conf = copy.deepcopy(red_item_conf)
                new_item_conf.cid = get_new_cid()
                new_item_conf.race_cid = new_race_cid
                new_item_conf.rule_cid = new_red_packet.cid
                new_item_conf.updated_id = user_cid
                award_map[red_item_conf.cid] = new_item_conf.cid
        if red_packet.category == 0:
            red_item_setting_list = await RedPacketItemSetting.find({'rule_cid': red_packet.cid, 'record_flag': 1}).to_list(None)
            red_item_basic = await RedPacketBasicSetting.find_one({'rule_cid': red_packet.cid, 'record_flag': 1})
            if red_item_setting_list and red_item_basic:
                #  奖项配置
                for red_item_setting in red_item_setting_list:
                    new_item_setting = copy.deepcopy(red_item_setting)
                    new_item_setting.cid = get_new_cid()
                    new_item_setting.race_cid = new_race_cid
                    new_item_setting.rule_cid = new_red_packet.cid
                    new_item_setting.updated_id = user_cid
                    new_item_setting_list.append(new_item_setting)
                #  基本配置
                new_item_basic = copy.deepcopy(red_item_basic)
                delattr(new_item_basic, 'id')
                new_item_basic.cid = get_new_cid()
                new_item_basic.race_cid = new_race_cid
                new_item_basic.rule_cid = new_red_packet.cid
                new_item_basic.updated_id = user_cid
                await new_item_basic.save()
        new_red_packet_list.append(new_red_packet)
        if new_item_conf:
            new_item_conf_list.append(new_item_conf)
    await RedPacketRule.insert_many(new_red_packet_list)
    await RedPacketConf.insert_many(new_item_conf_list)
    await RedPacketItemSetting.insert_many(new_item_setting_list)
    RedisCache.set(KEY_CACHE_RACE_COPY_MAP + race_cid + '_red_packet_copy', json.dumps(award_map))
    RedisCache.set(KEY_CACHE_RACE_COPY_MAP + race_cid + '_red_packet_rule_copy', json.dumps(red_rule_map))


async def do_copy_company(race_cid, new_race_cid, user_cid):
    """
    复制单位
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """
    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')
    old_company_cursor = Company.find({'race_cid': race_cid},
                                      read_preference=ReadPreference.PRIMARY).batch_size(32)
    new_company_list = []
    while await old_company_cursor.fetch_next:
        company = old_company_cursor.next_object()

        new_company = copy.deepcopy(company)
        new_company.cid = get_new_cid()
        new_company.race_cid = new_race_cid
        new_company.updated_id = user_cid

        new_company_list.append(new_company)

    await Company.insert_many(new_company_list)


async def do_copy_red_packet_box(race_cid, new_race_cid, user_cid):
    """
    复制红包奖池
    :param race_cid:
    :param new_race_cid:
    :param user_cid:
    :return:
    """
    if not race_cid or not new_race_cid or not user_cid:
        raise Exception('miss parameters')
    red_packet_item_list = await RedPacketItemSetting.find({'record_flag': 1, 'race_cid': new_race_cid}).to_list(None)
    red_packet_basic_list = await RedPacketBasicSetting.find_one({'record_flag': 1, 'race_cid': new_race_cid})
    red_packet_conf = await RedPacketConf.find_one({'record_flag': 1, 'race_cid': new_race_cid})
    if red_packet_item_list:
        await generate_awards_by_item_settings(red_packet_basic_list, red_packet_item_list)
    if red_packet_conf:
        await generate_awards_by_config(red_packet_conf)


async def get_menu(handler, flag, race_cid, tag=''):
    """

    :param handler:
    :param flag:
    :return:
    """
    user_menus = handler.session.get(KEY_SESSION_USER_MENU)
    if not user_menus:
        return
    menu_list = menu_utils.get_specified_menu(user_menus, flag=flag)
    race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
    if not tag:
        if not race.company_enabled and not race.town_enable:
            menu_list.pop()
    menu_list.sort(key=lambda menu: menu.weight)

    return menu_list

