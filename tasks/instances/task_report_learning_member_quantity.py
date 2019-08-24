"""
公民参与科学素质学习状况-人数
"""
import traceback

import msgpack

from caches.redis_utils import RedisCache
from db import STATUS_USER_ACTIVE
from db.models import AdministrativeDivision, Member, MemberLearningDayStatistics, \
    MemberGameHistory, MemberCheckPointHistory, MemberSubjectStatistics
from enums import KEY_CACHE_REPORT_DOING_NOW, KEY_CACHE_REPORT_ECHARTS_CONDITION
from logger import log_utils
from motorengine import DESC, FacadeO
from motorengine.stages import MatchStage, LookupStage, SortStage, ProjectStage
from motorengine.stages.add_fields_stage import AddFieldsStage
from motorengine.stages.group_stage import GroupStage
from tasks import app
from tasks.instances.utils import early_warning, early_warning_empty
from tasks.utils import save_cache_condition, get_yesterday, get_merge_city_data

logger = log_utils.get_logging('task_report_learning_member_quantity', 'task_report_learning_member_quantity.log')


@app.task(bind=True, queue='member_quantity')
def start_statistics_member_quantity(self, cache_key, city_code_list, choice_time):
    """启动任务

    :param self:
    :param cache_key:
    :param city_code_list:
    :param choice_time
    :return:
    """
    logger.info('[START] MEMBER_QUANTITY_STATISTICS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_member_quantity', cache_key=cache_key,
                             city_code_list=city_code_list, choice_time="")
        do_statistics_member_quantity(cache_key, city_code_list, choice_time)
    except Exception:
        logger.warning(
            '[ERROR] MEMBER_QUANTITY_STATISTICS(%s): cache_key=%s, city_code_list=%s\n %s' % (
                self.request.id, cache_key, str(city_code_list), traceback.format_exc()))
        early_warning(self.request.id, "MEMBER_QUANTITY_STATISTICS", cache_key, city_code_list, traceback.format_exc())
    logger.info('[ END ] MEMBER_QUANTITY_STATISTICS(%s)' % self.request.id)


def do_statistics_member_quantity(cache_key, city_code_list, choice_time):
    """开始统计

    :param cache_key:
    :param city_code_list:
    :param choice_time
    :return:
    """

    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)

    stage_list = []
    if city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': city_code_list}}))
    if not choice_time:
        #  取前一天凌晨12点之前的数据
        yesterday_time = get_yesterday()
        time_match = MatchStage({'updated_dt': {'$lt': yesterday_time}})
    else:
        #  当天下一天凌晨的时候
        max_choice_time = choice_time.replace(hour=23, minute=59, second=59, microsecond=999)
        time_match = MatchStage({'updated_dt': {'$gte': choice_time, '$lt': max_choice_time}})
    stage_list.append(time_match)
    stage_list.append(MatchStage({'status': STATUS_USER_ACTIVE}))
    group_stage = GroupStage('province_code', quantity={'$sum': 1})
    lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'ad_list')
    sort_stage = SortStage([('quantity', DESC)])

    stage_list += [group_stage, lookup_stage, sort_stage]
    province_cursor = Member.sync_aggregate(stage_list)
    province_dict = {}
    while True:
        try:
            province_stat = province_cursor.next()
            if province_stat:
                province_code = province_stat.id if province_stat.id else '000000'
                quantity = province_stat.quantity
                title = 'undefined'
                ad_list = province_stat.ad_list
                if ad_list:
                    ad: FacadeO = ad_list[0]
                    if ad:
                        title = ad.title.replace('省', '').replace('市', '')
                province_dict[province_code] = {
                    'code': province_code,
                    'title': title,
                    'data': quantity
                }
        except StopIteration:
            break
    # 合并城市统计信息
    do_merge_city_stat_member_quantity(province_dict, choice_time, city_code_list)

    data = [v for v in province_dict.values()]
    if not data:
        early_warning_empty("start_statistics_member_quantity", cache_key, city_code_list, '学习近况中人数数据为空，请检查！')
    RedisCache.set(cache_key, msgpack.packb(data))


def do_merge_city_stat_member_quantity(province_dict: dict, choice_time, city_code_list=None):
    """
    合并省份统计信息
    :param province_dict:
    :param city_code_list
    :param choice_time
    :return:
    """
    query_dict = {}
    if province_dict:
        query_dict['province_code'] = {'$in': [code for code in province_dict.keys()]}
        if city_code_list:
            query_dict['city_code'] = {'$in': city_code_list}
        else:
            query_dict['city_code'] = {'$ne': None}
        if not choice_time:
            #  取前一天凌晨12点之前的数据
            yesterday = get_yesterday()
            query_dict['updated_dt'] = {'$lt': yesterday}
        else:
            #  当天下一天凌晨的时候
            max_choice_time = choice_time.replace(hour=23, minute=59, second=59, microsecond=999)
            query_dict['updated_dt'] = {'$gte': choice_time, '$lt': max_choice_time}
        query_dict['status'] = STATUS_USER_ACTIVE
        match_stage = MatchStage(query_dict)
        group_stage = GroupStage('city_code', quantity={'$sum': 1}, province_code={'$first': '$province_code'})
        sort_stage = SortStage([('quantity', DESC)])
        p_lookup_stage = LookupStage(AdministrativeDivision, 'province_code', 'post_code', 'province_list')
        c_lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'city_list')

        city_cursor = Member.sync_aggregate([match_stage, group_stage, sort_stage, p_lookup_stage, c_lookup_stage])
        t_province_dict = {}
        t_province_dict = get_merge_city_data(city_cursor, province_dict, t_province_dict)
        if t_province_dict:
            province_dict.update(t_province_dict)


@app.task(bind=True, queue='member_time')
def start_statistics_member_time(self, cache_key, city_code_list, choice_time):
    """启动任务
    学习近况-公民参与科学素质学习状况-次数
    :param self:
    :param cache_key:
    :param city_code_list:
    :param choice_time
    :return:
    """
    logger.info('[START] MEMBER_TIME_STATISTICS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_member_time', cache_key=cache_key,
                             city_code_list=city_code_list, choice_time="")
        do_statistics_member_time(cache_key, city_code_list, choice_time)
    except Exception:
        logger.warning(
            '[ERROR] MEMBER_TIME_STATISTICS(%s): cache_key=%s, city_code_list=%s\n %s' % (
                self.request.id, cache_key, str(city_code_list), traceback.format_exc()))
        early_warning(self.request.id, "MEMBER_TIME_STATISTICS", cache_key, city_code_list, traceback.format_exc())
    logger.info('[ END ] MEMBER_TIME_STATISTICS(%s)' % self.request.id)


def do_statistics_member_time(cache_key, city_code_list, choice_time):
    """开始统计

    :param cache_key:
    :param city_code_list:
    :param choice_time:
    :return:
    """

    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW, 5 * 60)

    ad_map = {}
    game_data, ad_map = do_stat_in_history(MemberGameHistory, city_code_list, choice_time, ad_map)
    ckpt_data, ad_map = do_stat_in_history(MemberCheckPointHistory, city_code_list, choice_time, ad_map)

    #  对学习之旅和科协答题历史记录进行数据整合
    for k, city_dict in game_data.items():
        if k not in ckpt_data:
            ckpt_data[k] = city_dict
            continue

        # loop city_list
        for c_name, c_data in city_dict.items():
            try:
                # try to merge
                ckpt_data[k][c_name] += c_data
            except KeyError:
                ckpt_data[k][c_name] = c_data

    ret_data = []
    for prov_code, city_data in ckpt_data.items():
        prov = ad_map.get(prov_code)
        if not prov:
            prov = AdministrativeDivision.sync_find_one({'code': prov_code, 'parent_code': None})

        city_list = [{'title': _k, 'data': _v} for _k, _v in city_data.items()]
        _ds = [_.get('data') for _ in city_list]

        city_list.sort(key=lambda x: -x.get('data'))
        ret_data.append(
            {'title': prov.title.replace('省', '').replace('市', ''), 'data': sum(_ds), 'city_list': city_list})
    ret_data.sort(key=lambda x: -x.get('data'))
    if not ret_data:
        early_warning_empty("start_statistics_member_time", cache_key, city_code_list, '学习近况中次数数据为空，请检查！')

    RedisCache.set(cache_key, msgpack.packb(ret_data))


def do_stat_in_history(history_model, city_code_list, choice_time, ad_map={}):
    """

    :param history_model:
    :param city_code_list:
    :param ad_map:
    :param choice_time
    :return:
    """
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    if not choice_time:
        match_stage = MatchStage({'updated_dt': {'$lt': time_match}})
    else:
        #  当天下一天凌晨的时候
        max_choice_time = choice_time.replace(hour=23, minute=59, second=59, microsecond=999)
        match_stage = MatchStage({'updated_dt': {'$gte': choice_time, '$lt': max_choice_time}})
    cursor = history_model.sync_aggregate([
        match_stage,
        GroupStage('member_cid', quantity={"$sum": 1}),
        LookupStage(Member, '_id', 'cid', 'member_list'),
        ProjectStage(**{
            'province_code': {'$arrayElemAt': ['$member_list.province_code', 0]},
            'city_code': {'$arrayElemAt': ['$member_list.city_code', 0]},
            'quantity': '$quantity'
        }),
        MatchStage({'city_code': {'$in': city_code_list}}),
        GroupStage('city_code', quantity={'$sum': "$quantity"}, province_code={'$first': '$province_code'}),
        SortStage([('quantity', DESC)])
    ])

    data = {}
    while True:
        try:
            his = cursor.next()
            city_data = data.get(his.province_code, {})

            city = ad_map.get(his.id)
            if not city:
                city = AdministrativeDivision.sync_find_one({'code': his.id, 'parent_code': {'$ne': None}})
                ad_map[city.code] = city
            city_data[city.title] = his.quantity
            data[his.province_code] = city_data
        except StopIteration:
            break
        except Exception as e:
            logger.error(str(e))
            continue

    return data, ad_map


def do_merge_city_stat_member_time(province_dict: dict, city_code_list=None):
    """
    合并省份统计信息
    :param province_dict:
    :param city_code_list
    :return:
    """
    query_dict = {}
    if province_dict:
        query_dict['province_code'] = {'$in': [code for code in province_dict.keys()]}
        if city_code_list:
            query_dict['city_code'] = {'$in': city_code_list}
        else:
            query_dict['city_code'] = {'$ne': None}
        #  取前一天凌晨12点之前的数据
        time_match = get_yesterday()
        query_dict['updated_dt'] = {'$lt': time_match}
        match_stage = MatchStage(query_dict)
        group_stage = GroupStage('city_code', quantity={'$sum': '$learn_times'},
                                 province_code={'$first': '$province_code'})
        sort_stage = SortStage([('quantity', DESC)])
        p_lookup_stage = LookupStage(AdministrativeDivision, 'province_code', 'post_code', 'province_list')
        c_lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'city_list')

        city_cursor = MemberLearningDayStatistics.sync_aggregate(
            [match_stage, group_stage, sort_stage, p_lookup_stage, c_lookup_stage])
        t_province_dict = {}
        t_province_dict = get_merge_city_data(city_cursor, province_dict, t_province_dict)
        if t_province_dict:
            province_dict.update(t_province_dict)


@app.task(bind=True, queue='member_accuracy')
def start_statistics_member_accuracy(self, cache_key, city_code_list, choice_time):
    """

    :param self:
    :param cache_key:
    :param city_code_list:
    :param choice_time
    :return:
    """
    logger.info('[START] MEMBER_ACCURACY_STATISTICS(%s), cache_key=%s' % (self.request.id, cache_key))

    try:
        save_cache_condition('start_statistics_member_accuracy', cache_key=cache_key, city_code_list=city_code_list,
                             choice_time="")
        do_statistics_accuracy(cache_key, city_code_list, choice_time)
    except Exception:
        logger.warning(
            '[ERROR] MEMBER_ACCURACY_STATISTICS(%s): locals=%s\n %s' % (
                self.request.id, str(locals()), traceback.format_exc()))

    logger.info('[ END ] MEMBER_ACCURACY_STATISTICS(%s)' % self.request.id)


def do_statistics_accuracy(cache_key, city_code_list, choice_time):
    """
    学习状况-正确率
    :param cache_key:
    :param city_code_list:
    :param choice_time
    :return:
    """
    RedisCache.set(cache_key, KEY_CACHE_REPORT_DOING_NOW)
    #  取前一天凌晨12点之前的数据
    time_match = get_yesterday()
    if not choice_time:
        match_stage = MatchStage({'updated_dt': {'$lt': time_match}})
    else:
        #  当天下一天凌晨的时候
        max_choice_time = choice_time.replace(hour=23, minute=59, second=59, microsecond=999)
        match_stage = MatchStage({'updated_dt': {'$gte': choice_time, '$lt': max_choice_time}})
    stage_list = [match_stage]
    if city_code_list:
        stage_list.append(MatchStage({'city_code': {'$in': city_code_list}}))

    group_stage = GroupStage('province_code', t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'})
    add_fields_stage = AddFieldsStage(t_accuracy={
        '$cond':
            {
                'if': {'$eq': ['$t_total', 0]},
                'then': 0,
                'else':
                    {
                        '$divide': ['$t_correct', '$t_total']
                    }
            }
    })
    sort_stage = SortStage([('t_accuracy', DESC)])
    lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'ad_list')
    stage_list.extend([group_stage, add_fields_stage, sort_stage, lookup_stage])
    province_stat_list = MemberSubjectStatistics.sync_aggregate(stage_list)
    province_dict = {}
    while True:
        try:
            province_stat = province_stat_list.next()
            if province_stat:
                province_code = province_stat.id if province_stat.id else '000000'
                total = province_stat.t_total if province_stat.t_total else 0
                correct = province_stat.t_correct if province_stat.t_correct else 0
                title = 'undefined'
                ad_list = province_stat.ad_list
                if ad_list:
                    ad: FacadeO = ad_list[0]
                    if ad:
                        title = ad.title.replace('省', '').replace('市', '')
                province_dict[province_code] = {
                    'code': province_code,
                    'title': title,
                    'correct': correct,
                    'total': total,
                    'data': round(correct / total * 100 if total > 0 else 0, 2)
                }
        except StopIteration:
            break
    # 合并城市统计信息
    do_merge_city_stat_accuracy(province_dict, city_code_list)

    data = [v for v in province_dict.values()]
    RedisCache.set(cache_key, msgpack.packb(data))
    if not data:
        early_warning_empty("start_statistics_member_accuracy", cache_key, city_code_list, '学习近况中正确率数据为空，请检查！')
    return data


def do_merge_city_stat_accuracy(province_dict: dict, city_code_list=None):
    """
    合并省份统计信息
    :param province_dict:
    :param city_code_list:
    :return:
    """
    if province_dict:
        match_query = {'province_code': {'$in': [code for code in province_dict.keys()]}}
        if city_code_list:
            match_query['city_code'] = {'$in': city_code_list}
        else:
            match_query['city_code'] = {'$ne': None}
        match_stage = MatchStage(match_query)
        group_stage = GroupStage('city_code', t_total={'$sum': '$total'}, t_correct={'$sum': '$correct'},
                                 province_code={'$first': '$province_code'})
        add_fields_stage = AddFieldsStage(t_accuracy={
            '$cond':
                {
                    'if': {'$eq': ['$t_total', 0]},
                    'then': 0,
                    'else':
                        {
                            '$divide': ['$t_correct', '$t_total']
                        }
                }
        })
        sort_stage = SortStage([('t_accuracy', DESC)])
        p_lookup_stage = LookupStage(AdministrativeDivision, 'province_code', 'post_code', 'province_list')
        c_lookup_stage = LookupStage(AdministrativeDivision, '_id', 'post_code', 'city_list')
        city_stat_list = MemberSubjectStatistics.sync_aggregate(
            [match_stage, group_stage, add_fields_stage, sort_stage, p_lookup_stage, c_lookup_stage])
        t_province_dict = {}
        while True:
            try:
                city_stat = city_stat_list.next()
                if not city_stat:
                    continue
                city_list = city_stat.city_list
                total = city_stat.t_total if city_stat.t_total else 0
                correct = city_stat.t_correct if city_stat.t_correct else 0
                if not city_list:
                    continue
                city: FacadeO = city_list[0]
                if not (city and city.parent_code):
                    continue

                p_stat = province_dict.get(city.parent_code)
                if p_stat:
                    if p_stat.get('city_list') is None:
                        p_stat['city_list'] = []
                    p_stat['city_list'].append({
                        'code': city_stat.id,
                        'title': city.title,
                        'correct': correct,
                        'total': total,
                        'data': round(correct / total * 100 if total > 0 else 0, 2)
                    })
                else:
                    province_list = city_stat.province_list
                    if province_list:
                        province: FacadeO = province_list[0]
                        if province:
                            if t_province_dict.get(province.post_code) is None:
                                t_province_dict[province.post_code] = {
                                    'code': province.post_code,
                                    'title': province.title.replace('省', '').replace('市', ''),
                                    'correct': 0,
                                    'total': 0
                                }
                            t_province_dict[province.post_code]['correct'] += correct
                            t_province_dict[province.post_code]['total'] += total
                            t_province_dict['data'] = round(t_province_dict[province.post_code]['correct'] /
                                                            t_province_dict[province.post_code][
                                                                'total'] * 100 if
                                                            t_province_dict[province.post_code][
                                                                'total'] > 0 else 0, 2)

                            if t_province_dict[province.post_code].get('city_list') is None:
                                t_province_dict[province.post_code]['city_list'] = []
                            t_province_dict[province.post_code]['city_list'].append({
                                'code': city_stat.id,
                                'title': city.title,
                                'correct': correct,
                                'total': total,
                                'data': round(correct / total * 100 if total > 0 else 0, 2)
                            })
            except StopIteration:
                break

        if t_province_dict:
            province_dict.update(t_province_dict)


if __name__ == '__main__':
    print(RedisCache.smembers(KEY_CACHE_REPORT_ECHARTS_CONDITION))
