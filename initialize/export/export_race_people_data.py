#! /usr/bin/python


import pdb

import xlsxwriter
from db.enums import CATEGORY_MEMBER_DICT
from db.models import ReportRacePeopleStatistics, RedPacketBox, RedPacketItemSetting, RaceMapping, Member, Race, \
    AdministrativeDivision
from motorengine import ASC
from motorengine.stages import MatchStage, ProjectStage, LookupStage, SortStage
from motorengine.stages.group_stage import GroupStage

workbook = xlsxwriter.Workbook('贵州活动统计.xlsx')


def write_sheet(book, sheet_name, pre_match={}, count_type='$people_num'):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :param count_type:
    :return:
    """

    match = {'race_cid': '3040737C97F7C7669B04BC39A660065D'}
    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'district': '$district'}, sum={'$sum': count_type},
                             city={'$first': '$city'})
    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')
    daily_map = {}
    for index, daily_code in enumerate(daily_list):
        sheet.write_string(0, index + 2, daily_code)
        daily_map[daily_code] = index + 2

    district_list = ReportRacePeopleStatistics.sync_distinct('district', match)
    district_map = {}
    for index, district in enumerate(district_list):
        sheet.write_string(index + 1, 1, district if district else '其他')
        district_map[district if district else '其他'] = index + 1

    cursor = ReportRacePeopleStatistics.sync_aggregate([MatchStage(match), group_stage])

    county_map = dict()
    v_list = list()
    _max_row = 0
    while True:
        try:
            stat = cursor.next()

            city = stat.city if stat.city else '其他'
            district = stat.id.get('district')
            daily_code = stat.id.get('daily_code')

            _row = district_map.get(district if district else '其他')
            sheet.write_string(_row, 0, city)
            ad_city = AdministrativeDivision.sync_find_one({'title': city})
            _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
            for _c in _county:
                county_map[_c] = city

            sheet.write_number(_row, daily_map.get(daily_code), stat.sum)

            if _row > _max_row:
                _max_row = _row

            v_list.append(stat.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in district_map:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_important(book, sheet_name, pre_match={}, count_type='$people_num'):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :param count_type:
    :return:
    """

    match = {'race_cid': 'F742E0C7CA5F7E175844478D74484C29'}
    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'category': '$category'}, sum={'$sum': count_type})
    daily_list = ReportRacePeopleStatistics.sync_distinct('daily_code', match)

    daily_list.sort()

    sheet.write_string(0, 0, '重点人群')
    cursor = ReportRacePeopleStatistics.sync_aggregate(
        [MatchStage(match), group_stage, SortStage([('_id.daily_code', ASC)])])

    daily_list = []
    prize_list = []

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('category')
            title = 5 if not title else title
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, CATEGORY_MEMBER_DICT.get(title))
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_daily_incre_people(book, sheet_name='每日新增参与人数', pre_match={}):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :return:
    """
    race = Race.sync_find_one({'cid': 'F742E0C7CA5F7E175844478D74484C29'})
    _p = AdministrativeDivision.sync_find_one({'code': race.province_code, 'parent_code': None})

    match = {'race_cid': 'F742E0C7CA5F7E175844478D74484C29'}
    # if _p:
    #     match['auth_address.province'] = _p.title

    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         # LookupStage(Member, let={'cid': '$member_cid'}, as_list_name='member_list', pipeline=[{'$match': {
         #     '$expr': {'$and': [{'$eq': ['$cid', '$$cid']}, {'$eq': ['$auth_address.province', _p.title]}]}}}]),
         # MatchStage({'member_list': {'$ne': []}}),

         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             #'auth_address': {'$arrayElemAt': ['$member_list.auth_address', 0]}
             'auth_address': "$auth_address"
         }), GroupStage({'daily_code': '$daily_code', 'district': '$auth_address.district'}, sum={'$sum': 1},
                        auth_address={'$first': '$auth_address'}),
         SortStage([('_id.daily_code', ASC)])])

    sheet.write_string(0, 0, '城市')
    sheet.write_string(0, 1, '区县')

    daily_list = []
    prize_list = []
    county_map = {}

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('district')
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                city = data.auth_address.get('city')
                sheet.write_string(_current_row, 0, city)
                ad_city = AdministrativeDivision.sync_find_one({'title': city})
                _county = AdministrativeDivision.sync_distinct('title', {'parent_code': ad_city.code})
                for _c in _county:
                    county_map[_c] = city

                sheet.write_string(_current_row, 1, title)

            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list) + 1
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 2

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    for k, v in county_map.items():
        if k not in prize_list:
            _max_row += 1
            sheet.write_string(_max_row, 0, v)
            sheet.write_string(_max_row, 1, k)

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))


def is_prov_valid(race: Race, prov: str):
    """

    :param race:
    :param prov:
    :return:
    """

    if not prov:
        # 暂时为True
        return True

    _p = AdministrativeDivision.sync_find_one({'title': {'$regex': prov}, 'parent_code': None})
    if _p.code == race.province_code:
        return True
    else:
        return False


def write_sheet_important_people(book, sheet_name, pre_match={}, count_type='$people_num'):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :param count_type:
    :return:
    """

    match = {'race_cid': 'F742E0C7CA5F7E175844478D74484C29'}
    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    group_stage = GroupStage({'daily_code': '$daily_code', 'category': '$category'}, sum={'$sum': count_type})
    cursor = ReportRacePeopleStatistics.sync_aggregate(
        [MatchStage(match), group_stage, SortStage([('_id.daily_code', ASC)])])

    daily_list = []
    prize_list = []

    _max_row = 0
    v_list = list()
    while True:
        try:
            redpkt = cursor.next()
            _current_row = None

            title = redpkt.id.get('category')
            title = 5 if not title else title
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, CATEGORY_MEMBER_DICT.get(title))
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = redpkt.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1

            if _current_row >= _max_row:
                _max_row = _current_row

            sheet.write_number(_current_row, _current_col, redpkt.sum)

            v_list.append(redpkt.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


def write_sheet_daily_incre_people_important(book, sheet_name, pre_match={}):
    """

    :param book:
    :param sheet_name:
    :param pre_match:
    :return:
    """
    race = Race.sync_find_one({'cid': 'F742E0C7CA5F7E175844478D74484C29'})
    _p = AdministrativeDivision.sync_find_one({'code': race.province_code, 'parent_code': None})

    match = {'race_cid': 'F742E0C7CA5F7E175844478D74484C29'}
    # if _p:
    #     match['auth_address.province'] = _p.title

    if pre_match:
        match.update(pre_match)
    sheet = book.add_worksheet(sheet_name)

    cursor = RaceMapping.sync_aggregate(
        [MatchStage(match),
         ProjectStage(**{
             'daily_code': {'$dateToString': {'format': "%Y%m%d", 'date': "$created_dt"}},
             'category': '$category'
         }), GroupStage({'daily_code': '$daily_code', 'category': '$category'}, sum={'$sum': 1}),
         SortStage([('_id.daily_code', ASC)])])

    sheet.write_string(0, 0, '重点人群')

    daily_list = []
    prize_list = []

    v_list = list()
    _max_row = 0
    while True:
        try:
            data = cursor.next()
            _current_row = None

            title = data.id.get('category')
            title = 5 if not title else title
            if title is None:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, CATEGORY_MEMBER_DICT.get(title))
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = data.id.get('daily_code')
            if not daily_code:
                daily_code = '未知'
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1

            sheet.write_number(_current_row, _current_col, data.sum)

            v_list.append(data.sum)
            if _current_row >= _max_row:
                _max_row = _current_row

        except StopIteration:
            break
        except Exception as e:
            raise e

    if _max_row:
        sheet.write_string(_max_row + 1, 0, '总和')
        sheet.write_number(_max_row + 1, 1, sum(v_list))


#
# class RedPacketBox(BaseModel):
#     race_cid = StringField(required=True)  # 竞赛活动cid信息
#     rule_cid = StringField(required=True)  # 红包规则cid信息
#     award_cid = StringField()  # 奖品RedPacketItemSetting.cid信息，None == 谢谢惠顾
#     award_msg = StringField()  # 奖励信息
#     award_amount = FloatField(default=0.0)  # 奖励金额
#
#     checkpoint_cid = StringField()  # 竞赛关卡cid
#     draw_status = IntegerField(default=STATUS_REDPACKET_NOT_AWARDED, choice=STATUS_REDPACKET_AWARD_LIST)  # 是否被领取
#     member_cid = StringField()  # 领取人的open_id
#     draw_dt = DateTimeField()  # 领取时间, 领走
#     redpkt_rid = StringField()  # 订单号
#     request_dt = DateTimeField(default=datetime.now)  # 向红包平台请求发红包的时间， 拆的时间
#     request_status = IntegerField()  # 请求是否成功
#     # issue_status = IntegerField()  # 发放状态
#     error_msg = StringField()  # 错误信息

def write_sheet_redpkt(book, sheet_name):
    """

    :param book:
    :param sheet_name:
    :return:
    """

    match = {'race_cid': 'F742E0C7CA5F7E175844478D74484C29', 'award_cid': {'$ne': None}, 'draw_dt': {'$ne': None},
             'draw_status': 0}

    sheet = book.add_worksheet(sheet_name)

    cursor = RedPacketBox.sync_aggregate([
        MatchStage(match),
        LookupStage(RedPacketItemSetting, 'award_cid', 'cid', 'award_list'),
        ProjectStage(**{
            'draw_dt': {'$dateToString': {'format': "%Y%m%d", 'date': "$draw_dt"}},
            'award_title': {'$arrayElemAt': ['$award_list.title', 0]},
            'award_amount': '$award_amount',
            'redpkt_id': '$_id'

        }),
        GroupStage({'daily_code': '$draw_dt', 'award_title': '$award_title'}, sum={'$sum': 1},
                   redpkt_id={'$first': '$redpkt_id'}),
        SortStage([('_id.daily_code', ASC)])
    ])

    daily_list = []
    prize_list = []

    _max_row = 0
    v_list = list()
    while True:
        try:
            redpkt = cursor.next()
            _current_row = None

            title = redpkt.id.get('award_title')
            if not title:
                title = '未知'

            if title not in prize_list:
                prize_list.append(title)
                _current_row = len(prize_list)
                sheet.write_string(_current_row, 0, title)
            else:
                _current_row = prize_list.index(title) + 1

            daily_code = redpkt.id.get('daily_code')
            if not daily_code:
                daily_code = '暂未领取'
                print(redpkt.redpkt_id)
            if daily_code not in daily_list:
                daily_list.append(daily_code)
                _current_col = len(daily_list)
                sheet.write_string(0, _current_col, daily_code)
            else:
                _current_col = daily_list.index(daily_code) + 1

            sheet.write_number(_current_row, _current_col, redpkt.sum)

            if _current_row >= _max_row:
                _max_row = _current_row

            v_list.append(redpkt.sum)
        except StopIteration:
            break
        except Exception as e:
            raise e

    sheet.write_string(_max_row + 1, 0, '总和')
    sheet.write_number(_max_row + 1, 1, sum(v_list))


from datetime import datetime

now = datetime.now()

# write_sheet(workbook, '每日参与人数', pre_match={'updated_dt': {'$lte': now}})
# write_sheet_daily_incre_people(workbook, '每日新增参与人数', pre_match={'updated_dt': {'$lte': now}})
write_sheet(workbook, '每日参与人次', pre_match={'updated_dt': {'$lte': now}}, count_type='$total_num')
# write_sheet(workbook, '每日新增通关人数', pre_match={'updated_dt': {'$lte': now}}, count_type='$pass_num')
#
# write_sheet_important(workbook, '重点人群每日参与人数（总）', pre_match={'updated_dt': {'$lte': now}})
# write_sheet_daily_incre_people_important(workbook, '重点人群每日新增参与人数（总）', pre_match={'updated_dt': {'$lte': now}})
# write_sheet_important_people(workbook, '重点人群每日参与人次（总）', pre_match={'updated_dt': {'$lte': now}}, count_type='$total_num')
# write_sheet_important(workbook, '重点人群每日新增通关人数（总）', pre_match={'updated_dt': {'$lte': now}}, count_type='$pass_num')
#
# # write_sheet_important_people(workbook, '重点人群每日参与人次（总）', {}, '$total_num')
# # write_sheet_important_people(workbook, '重点人群每日新增通关人数（总）', {}, '$pass_num')
# #
# write_sheet_redpkt(workbook, '每日中奖人数')
#
# for k, v in CATEGORY_MEMBER_DICT.items():
#     write_sheet(workbook, '重点人群(%s)每日参与人数' % v, {'category': k})
#     write_sheet(workbook, '重点人群(%s)每日参与人次' % v, {'category': k}, '$total_num')
#     write_sheet(workbook, '重点人群(%s)每日新增通关人次' % v, {'category': k}, '$pass_num')

workbook.close()
