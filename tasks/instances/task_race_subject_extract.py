#!/usr/bin/python


import copy
import datetime
import traceback

from pymongo import ReadPreference

from beans import DimensionRuleO, DimensionConditionO, RaceSubjectFilterO
from caches.redis_utils import RedisCache
from commons.common_utils import combination
from db import STATUS_SUBJECT_CHOICE_RULE_INACTIVE, CATEGORY_SUBJECT_DIMENSION_OPTIONS, \
    CATEGORY_SUBJECT_DIMENSION_WEIGHT, CATEGORY_SUBJECT_DIMENSION_NUMERICAL, STATUS_SUBJECT_CHOICE_RULE_ACTIVE
from db.models import SubjectDimension, RaceSubjectChoiceRules, RaceSubjectBanks, RaceGameCheckPoint
from enums import KEY_PREFIX_EXTRACTING_SUBJECT_RULE, KEY_PREFIX_SUBJECT_BANKS_COUNT, KEY_EXTRACTING_SUBJECT_QUANTITY
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage
from tasks import app

logger = log_utils.get_logging('task_race_subject_choice', 'task_race_subject_choice.log')


@app.task(bind=True, queue='race_subject_extract')
def start_race_extract_subjects(self, race_cid, race_subject_choice_rule: RaceSubjectChoiceRules):
    try:
        logger.info('START(%s): rules_cid=%s' % (self.request.id, race_subject_choice_rule.cid))
        cut_off_datetime = datetime.datetime.now()

        # 抽题
        def extract():
            extract_subjects(race_cid, race_subject_choice_rule)

        while True:
            extract()
            count = RaceSubjectBanks.sync_count(
                dict(race_cid=race_cid, rule_cid=race_subject_choice_rule.cid), read_preference=ReadPreference.PRIMARY)
            if count >= 4096:
                break
        # 删除旧题库
        RaceSubjectBanks.sync_delete_many(
            dict(race_cid=race_cid, rule_cid=race_subject_choice_rule.cid, choice_dt={'$lt': cut_off_datetime}))
        logger.info('END(%s): rules_cid=%s' % (self.request.id, race_subject_choice_rule.cid))

    except Exception:
        logger.error(traceback.format_exc())
    finally:
        # 删除题库数量缓存
        RedisCache.hdel(KEY_EXTRACTING_SUBJECT_QUANTITY, race_subject_choice_rule.cid)
        # 删除抽题状态
        RedisCache.hdel(KEY_PREFIX_EXTRACTING_SUBJECT_RULE, race_subject_choice_rule.cid)
        # 删除数量缓存
        RedisCache.delete('%s_%s' % (KEY_PREFIX_SUBJECT_BANKS_COUNT, race_subject_choice_rule.cid))


async def is_valid_extract_rule(race_subject_choice_rule: RaceSubjectChoiceRules, race_cid):
    """
    确认是否为有效抽题规则
    :param subject_choice_rule: 抽题规则
    :return:
    """
    if race_subject_choice_rule and race_subject_choice_rule.status == STATUS_SUBJECT_CHOICE_RULE_ACTIVE:
        filter_objects, options_dimension_list = calculate_subjects_filter_objects(race_subject_choice_rule, race_cid)
        if filter_objects:
            for fo in filter_objects:
                quantity = await fo.subject_group_quantity()
                if quantity > 0:
                    return True
        else:
            # 规则只包含【选项涵盖】
            if options_dimension_list:
                fo = RaceSubjectFilterO(race_cid)
                fo.sample_quantity = race_subject_choice_rule.quantity
                padding_option_filter([fo], options_dimension_list)
                quantity = await fo.subject_group_quantity()
                if quantity > 0:
                    return True
    return False


def extract_subjects(race_cid, race_subject_choice_rule: RaceSubjectChoiceRules):
    """
    完成一次题目抽样抽样
    :param subject_choice_rule: 抽样规则
    :return:
    """
    if race_subject_choice_rule and race_subject_choice_rule.status == STATUS_SUBJECT_CHOICE_RULE_ACTIVE:
        filter_objects, options_dimension_list = calculate_subjects_filter_objects(race_subject_choice_rule, race_cid)
        if filter_objects:
            for fo in filter_objects:
                extract_sample_single(race_cid, race_subject_choice_rule, fo)
        else:
            # 规则只包含【选项涵盖】
            if options_dimension_list:
                fo = RaceSubjectFilterO(race_cid=race_cid)
                fo.sample_quantity = race_subject_choice_rule.quantity
                padding_option_filter([fo], options_dimension_list)
                extract_sample_single(race_cid, race_subject_choice_rule, fo)


def extract_sample_single(race_cid, race_subject_choice_rule: RaceSubjectChoiceRules, filter_object: RaceSubjectFilterO):
    """
    单一抽样
    :param subject_choice_rule: 抽题规则
    :param filter_object: 筛选条件
    :return:
    """
    try:
        grouped_subject_cid_list = filter_object.grouped_subject_cid_list
        if grouped_subject_cid_list:
            counter = 0
            subject_bank_list = []
            for subject_cid_list in grouped_subject_cid_list:
                race_subject_bank = RaceSubjectBanks(race_cid=race_cid, rule_cid=race_subject_choice_rule.cid,
                                                     quantity=race_subject_choice_rule.quantity)
                race_subject_bank.refer_subject_cid_list = subject_cid_list
                race_subject_bank.choice_dt = datetime.datetime.now()
                race_subject_bank.race_cid = race_cid
                subject_bank_list.append(race_subject_bank)
                if counter > 320:
                    RaceSubjectBanks.sync_insert_many(subject_bank_list)
                    del subject_bank_list[:]
                    counter = 0
                counter += 1
            if subject_bank_list:
                RaceSubjectBanks.sync_insert_many(subject_bank_list)
    except Exception:
        logger.error(traceback.format_exc())


def calculate_subjects_filter_objects(race_choice_rule: RaceSubjectChoiceRules, race_cid: str):
    filter_objects = []
    options_dimension_list = []
    try:
        choice_dimension_list = get_choice_dimension_list(race_choice_rule)
        if choice_dimension_list:
            filter_list = []
            for choice_dimension in choice_dimension_list:
                # 暂存选项涵盖规则
                if choice_dimension.category == CATEGORY_SUBJECT_DIMENSION_OPTIONS:
                    options_dimension_list.append(choice_dimension)
                    continue
                # 转化权重
                change_weight_2_quantity(choice_dimension)
                # 删除无效条件
                delete_invalid_condition(choice_dimension)
                if choice_dimension.category in [CATEGORY_SUBJECT_DIMENSION_WEIGHT,
                                                 CATEGORY_SUBJECT_DIMENSION_NUMERICAL]:
                    filter_list.append(choice_dimension.sampling_condition_list)
            if filter_list:
                filter_objects = get_subject_filter_objects(race_cid, *filter_list)
                # 填充选项覆盖条件
                padding_option_filter(filter_objects, options_dimension_list)
    except Exception:
        pass
    return filter_objects, options_dimension_list


def get_choice_dimension_list(race_choice_rule: RaceSubjectChoiceRules):
    """
    获取规则维度信息
    :param choice_rule:
    :return:
    """
    result_list = []
    try:
        if race_choice_rule and race_choice_rule.dimension_rules:
            dimension_cid_list = list(race_choice_rule.dimension_rules.keys())
            if dimension_cid_list:
                match_stage = MatchStage({'cid': {'$in': dimension_cid_list}, 'parent_cid': None})
                lookup_stage = LookupStage(SubjectDimension, 'cid', 'parent_cid', 'dimension_list')
                subject_dimension_list = SubjectDimension.sync_aggregate([match_stage, lookup_stage]).to_list(None)
                for subject_dimension in subject_dimension_list:
                    # 获取抽样条件
                    dimension_rule = get_sampling_condition(subject_dimension,
                                                            race_choice_rule.dimension_rules.get(subject_dimension.cid),
                                                            race_choice_rule.quantity)
                    if dimension_rule:
                        result_list.append(dimension_rule)
    except Exception:
        logger.error(traceback.format_exc())
    return result_list


def get_sampling_condition(subject_dimension: SubjectDimension, dimension_value: dict, subject_quantity: int = 0):
    """
    获取抽样条件
    :param subject_dimension: 维度
    :param dimension_value: 规则维度设置的值
    :param subject_quantity: 抽样数量
    :return:
    """
    try:
        if subject_dimension and dimension_value and subject_quantity > 0:
            dimension_list = getattr(subject_dimension, 'dimension_list', [])
            if dimension_list:
                dimension_rule = DimensionRuleO(subject_dimension.cid, subject_dimension.category,
                                                subject_quantity=subject_quantity)
                for dimension in dimension_list:
                    if dimension:
                        dco = DimensionConditionO('%s->%s' % (dimension.parent_cid, dimension.cid))
                        value = dimension_value.get(dimension.cid)
                        if value is None:
                            if subject_dimension.category == CATEGORY_SUBJECT_DIMENSION_OPTIONS:
                                dco.value = False
                            else:
                                dco.value = 0
                        else:
                            dco.value = value
                        # 剔除值为0、False, None, ''的条件
                        if dco.value:
                            dimension_rule.append_sampling_condition(dco)
                if dimension_rule.sampling_condition_list:
                    return dimension_rule
    except Exception:
        logger.error(traceback.format_exc())
    return None


def delete_subjects(race_cid, race_choice_rule: RaceSubjectChoiceRules):
    """
    删除题目内容
    :param choice_rule: 抽题规则
    :return: bool
    """
    try:
        if race_choice_rule and race_choice_rule.status == STATUS_SUBJECT_CHOICE_RULE_INACTIVE:
            RaceSubjectBanks.sync_delete_many({'race_cid': race_cid, 'rule_cid': race_choice_rule.cid})
            return True
    except Exception:
        logger.error(traceback.format_exc())
    return False


def get_game_check_point_rules(race_cid, race_check_point_cid=None):
    """
    获取关卡抽题规则
    :param check_point_cid:
    :return:
    """
    try:
        cp_cid_list = []
        if race_check_point_cid:
            cp_cid_list.append(race_check_point_cid)
        else:
            cid_list = RaceGameCheckPoint.sync_distinct('rule_cid', {'race_cid': race_cid, 'rule_cid': {'$ne': None}})
            if cid_list:
                cp_cid_list.extend(cid_list)

        if cp_cid_list:
            race_rule_list = RaceSubjectChoiceRules.sync_find(
                {'race_cid': race_cid, 'cid': {'$in': cp_cid_list}}).to_list(None)
            if race_rule_list:
                return race_rule_list
    except Exception:
        logger.error(traceback.format_exc())
    return None


def change_weight_2_quantity(dimension_rule: DimensionRuleO):
    """
    将权重转换成题目数
    :param dimension_rule:
    :return:
    """
    if dimension_rule and dimension_rule.category == CATEGORY_SUBJECT_DIMENSION_WEIGHT:
        subject_quantity = dimension_rule.subject_quantity
        sampling_condition_list = dimension_rule.sampling_condition_list
        if sampling_condition_list:
            length = len(sampling_condition_list)
            sum = 0
            for sampling_condition in sampling_condition_list:
                sum += sampling_condition.value
            total_quantity = 0
            for index, sampling_condition in enumerate(sampling_condition_list):
                if index == length - 1:
                    sampling_condition.value = subject_quantity - total_quantity
                else:
                    value = int(sampling_condition.value / sum * subject_quantity)
                    sampling_condition.value = value
                    total_quantity += value


def delete_invalid_condition(dimension_rule: DimensionRuleO):
    """
    清除无效的条件
    :param dimension_rule:
    :return:
    """
    if dimension_rule and dimension_rule.category in [CATEGORY_SUBJECT_DIMENSION_WEIGHT,
                                                      CATEGORY_SUBJECT_DIMENSION_NUMERICAL]:
        sampling_condition_list = dimension_rule.sampling_condition_list
        if sampling_condition_list:
            index = 0
            while True:
                if index >= len(sampling_condition_list) - 1:
                    break
                if sampling_condition_list[index].value <= 0:
                    del sampling_condition_list[index]
                else:
                    index += 1


def padding_option_filter(filter_o_list, option_filter_list):
    """
    填充选项涵盖条件
    :param filter_o_list:
    :param option_filter_list:
    :return:
    """
    if filter_o_list and option_filter_list:
        option_condition_list = []
        for option_filter in option_filter_list:
            option_cid_list = []
            for sampling_condition in option_filter.sampling_condition_list:
                if sampling_condition.value:
                    option_cid_list.append(sampling_condition.cid.split('->')[1])
            if option_cid_list:
                option_condition_list.append((option_filter.cid, option_cid_list))

        if option_condition_list:
            for filter_o in filter_o_list:
                filter_o.extend_option_condition_list(option_condition_list)


def calculate_choice_combination(elements) -> list:
    """
    计算组合方式
    :param elements:
    :return:
    """
    result_list = []
    length = len(elements)
    if length > 1:
        index = 1
        while True:
            if index == 1:
                result_list = cross_two_list(elements[index - 1], elements[index])
            else:
                result_list = cross_two_list(result_list, elements[index])
            index += 1
            if index >= length:
                break
    elif length == 1:
        for element in elements[0]:
            result_list.append({element.cid: element.value})
    return result_list


def cross_two_list(first_list: list, second_list: list) -> list:
    """
    交叉两个数组
    :param first_list: 数组1
    :param second_list: 数组2
    :return:
    """
    f_result_list = []
    if first_list and second_list:
        for first in first_list:
            result_list = []
            take_out_quantity = get_target_quantity(first)
            adjust_target_list(result_list, second_list, take_out_quantity)
            if isinstance(first, DimensionConditionO):
                f_result_list.append([{first.cid: first.value}] + unwind_result_list(result_list))
            else:
                f_result_list.append(first + unwind_result_list(result_list))
    return f_result_list


def adjust_target_list(result_list, target_list: list, take_out_quantity):
    """
    调整目标结构同时计算组合结果
    :param result_list:
    :param target_list:
    :param take_out_quantity:
    :return:
    """
    if result_list is None:
        result_list = []
    if target_list and take_out_quantity:
        target = target_list[0]
        target_quantity = get_target_quantity(target)
        if target_quantity < take_out_quantity:
            target.value = target.value - target_quantity
            result_list.append({target.cid: target_quantity})
            del target_list[0]
            adjust_target_list(result_list, target_list, take_out_quantity - target_quantity)
        else:
            target.value = target.value - take_out_quantity
            result_list.append({target.cid: take_out_quantity})
            if target.value <= 0:
                del target_list[0]


def get_target_quantity(target) -> int:
    """
    获取目标剩余可抽数量
    :param target: 目标对象
    :return:
    """
    if target:
        if isinstance(target, (tuple, list)):
            return get_target_quantity(target[0])
        elif isinstance(target, DimensionConditionO):
            return target.value
    return 0


def unwind_result_list(target_list: list) -> list:
    """
    展开数组
    :param target_list: 需要展开的数组
    :return:
    """
    result_list = []
    if target_list:
        for target in target_list:
            if isinstance(target, list):
                result_list.extend(unwind_result_list(target))
            else:
                result_list.append(target)
    return result_list


def get_subject_filter_objects(race_cid, *condition_rules):
    """
    获取所有符合结果的筛选条件对象
    :param condition_rules:
    :return:
    """
    result_list = []
    try:
        if len(condition_rules) > 1:
            cached_list = []
            # i = 0
            comb_list = combination(*condition_rules)
            for comb in comb_list:
                deep_comb = copy.deepcopy(comb)
                choice_list = calculate_choice_combination(deep_comb)
                if choice_list:
                    sfo = RaceSubjectFilterO(race_cid=race_cid)
                    for choice in choice_list:
                        sfo.append_condition(choice)
                    if sfo.union_id not in cached_list:
                        cached_list.append(sfo.union_id)
                        # i += 1
                        result_list.append(sfo)
        elif len(condition_rules) == 1:
            sfo = RaceSubjectFilterO(race_cid=race_cid)
            for choice in condition_rules[0]:
                sfo.append_condition([{choice.cid: choice.value}])
            result_list.append(sfo)
    except Exception as e:
        raise e
    return result_list
