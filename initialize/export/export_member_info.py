# !/usr/bin/python
# -*- coding:utf-8 -*-


from datetime import datetime
import threading

import xlsxwriter

from commons.common_utils import str2datetime
from db.models import RaceMapping, Member, MemberCheckPointHistory, RaceGameCheckPoint, RedPacketBox, Race, BaseModel, \
    AdministrativeDivision
from motorengine import StringField, DESC, ReadPreference, ASC
from motorengine.fields import IntegerField, FloatField
from motorengine.stages import GroupStage, MatchStage, ProjectStage, LookupStage


class RaceStatisticInfo(BaseModel):
    race_cid = StringField(required=True)  # 竞赛活动cid信息
    daily_code = StringField(required=True)  # 日期
    total_member_count = IntegerField(default=0)  # 总会员人数
    total_answer_times = IntegerField(default=0)  # 总答题数
    total_red_packet_count = IntegerField(default=0)  # 总红包数
    total_red_packet_amount = FloatField(default=0.0)  # 总红包金额
    add_member_count = IntegerField(default=0)  # 新增人数
    add_answer_times = IntegerField(default=0)  # 新增答题数
    add_red_packet_count = IntegerField(default=0)  # 新增红包数
    add_red_packet_amount = FloatField(default=0.0)  # 新增红包金额


class MemberInfoExportedModel():
    # 基础信息
    open_id = None
    member_cid = None
    nick = None
    firstTimeOfEnroll = None
    city = None
    district = None
    mobile = ''
    currentCheckPoint = None
    # 统计信息
    answerTimes = 0  # 答题次数
    totalNumOfRedPacket = 0  # 领取红包数
    totalAmountOfRedPacket = 0  # 领取红包金额

    def __str__(self):
        return ','.join(['%s:%s' % item for item in self.__dict__.items()])


class MyThread(threading.Thread):
    def __init__(self, target, args=()):
        super(MyThread, self).__init__()
        self.target = target
        self.args = args

    def run(self):
        self.result = self.target(*self.args)

    def get_result(self):
        try:
            return self.result
        except Exception:
            return None


def splitList(listTemp, n):
    for i in range(0, len(listTemp), n):
        yield listTemp[i:i + n]


def get_member_info(thread_num, race_member_list, checkPointCidList, lastCheckPoint, checkPointMap):
    exportedMemberList = []
    for race_member in race_member_list:
        # raceMapping = race_member.race_list[0]
        raceMapping = race_member
        race_cid = raceMapping.race_cid
        member = race_member.member_list[0]
        memberCid = member.cid

        red_match = MatchStage(
            {'race_cid': race_cid, 'member_cid': memberCid, 'draw_status': 0, 'draw_dt': {'$ne': None},
             'award_cid': {'$ne': None}, 'record_flag': 1})
        red_project = ProjectStage(**{"member_cid": 1, "award_amount": 1})
        red_group = GroupStage('member_cid', count={'$sum': 1}, amount={'$sum': '$award_amount'})
        # redPacketsOfMember = RedPacketBox.sync_find(
        #     {'race_cid': race_cid, 'member_cid': memberCid, 'award_cid': {'$ne': None}, 'record_flag': 1})
        # eachAmountOfRedPacket = [redPacket.award_amount for redPacket in redPacketsOfMember]
        redPacketsOfMemberCursor = RedPacketBox.sync_aggregate([red_match, red_project, red_group]).batch_size(50)
        exportedMember = MemberInfoExportedModel()
        exportedMember.open_id = member.open_id
        exportedMember.member_cid = memberCid
        exportedMember.nick = member.nick_name
        exportedMember.firstTimeOfEnroll = member.created_dt
        city = raceMapping.auth_address.get('city', '')
        exportedMember.city = city if not city is None else ''
        district = raceMapping.auth_address.get('district', '')
        exportedMember.district = district if not district is None else ''
        mobile = getattr(raceMapping, 'mobile', '')
        if mobile is None:
            exportedMember.mobile = member.mobile
        else:
            exportedMember.mobile = mobile
        check_point_cid = getattr(raceMapping, 'race_check_point_cid', None)
        if check_point_cid is None:
            exportedMember.currentCheckPoint = "1"
        elif check_point_cid == lastCheckPoint:
            exportedMember.currentCheckPoint = "已通关"
        else:
            exportedMember.currentCheckPoint = str(checkPointMap[check_point_cid])
        answerTimes = MemberCheckPointHistory.sync_find(
            {'member_cid': memberCid, 'check_point_cid': {'$in': checkPointCidList}, 'record_flag': 1}).to_list(None)
        exportedMember.answerTimes = len(answerTimes)
        try:
            redPacketsOfMember = redPacketsOfMemberCursor.next()
            if redPacketsOfMember:
                exportedMember.totalNumOfRedPacket = redPacketsOfMember.count
                exportedMember.totalAmountOfRedPacket = round(redPacketsOfMember.amount, 2)
        except StopIteration:
            pass

        exportedMemberList.append(exportedMember)
        print(thread_num, member.cid, exportedMember.nick, exportedMember.city, exportedMember.district,
              exportedMember.mobile,
              exportedMember.currentCheckPoint, exportedMember.answerTimes, exportedMember.totalNumOfRedPacket,
              exportedMember.totalAmountOfRedPacket)
    return exportedMemberList


def statistic_member_info(race_cid: str, province_code, yesterday):
    """
    会员信息导入，只根据race_mapping表中race_cid删选,没有过滤address为空的
    :param race_cid:
    :return:
    """
    city_code_list = AdministrativeDivision.sync_distinct('code', {'parent_code': province_code})
    city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': province_code})
    district_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': {'$in': city_code_list}})

    # race_member_match = {"race_cid": race_cid, 'record_flag': 1, 'auth_address.province': {'$ne': None},
    #                      'auth_address.city': {"$in": city_name_list},
    #                      'auth_address.district': {"$in": district_name_list},
    #                      'created_dt': {'$lte': datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)}}
    # race_member_match = {"race_cid": race_cid, 'record_flag': 1, 'auth_address.province': {'$ne': None},
    #                      'auth_address.city': {"$in": city_name_list},
    #                      'auth_address.district': {"$in": district_name_list},
    #                      'created_dt': {'$lte': yesterday}}
    match = {"race_cid": race_cid, 'record_flag': 1}
    # 当前活动参与会员
    # memberCidList = RaceMapping.sync_distinct("member_cid", race_member_match)
    cursor = RaceMapping.sync_aggregate([
        MatchStage(
            {'race_cid': race_cid, 'auth_address.province': {'$ne': None}, "record_flag": 1,
             'auth_address.city': {"$in": city_name_list},
             'auth_address.district': {"$in": district_name_list},
             'created_dt': {'$lte': yesterday}}),
        # GroupStage({'member_cid': '$member_cid'}, race_list={'$push': '$$ROOT'}),
        LookupStage(Member, 'member_cid', 'cid', 'member_list'),
        MatchStage({'member_list': {'$ne': []}})
    ], allowDiskUse=True)
    # memberCidList.sort()
    # 当前活动关卡cid
    checkPointList = RaceGameCheckPoint.sync_aggregate([MatchStage(match)])
    checkPointMap = {}
    lastCheckPoint = None
    maxCheckPointIndex = 0
    for check_point in checkPointList:
        checkPointMap[check_point.cid] = check_point.index
        if check_point.index > maxCheckPointIndex:
            maxCheckPointIndex = check_point.index
            lastCheckPoint = check_point.cid
    checkPointCidList = list(checkPointMap.keys())

    # print("该活动下的会员", len(memberCidList), memberCidList)
    # print("该活动下的会员数", len(set(memberCidList)))
    # print("该活动下的关卡", len(checkPointCidList), checkPointCidList)
    race_member_list = []
    for race_member in cursor:
        race_member_list.append(race_member)
    print("会员总人数", len(race_member_list))
    temp_list = splitList(race_member_list, 1000)
    threads = []
    thread_num = 1

    for my_list in temp_list:
        print("开启个线程处理会员数", len(my_list))
        t = MyThread(get_member_info,
                     args=(thread_num, my_list, checkPointCidList, lastCheckPoint, checkPointMap))
        threads.append(t)
        thread_num += 1
        # break

    for my_thread in threads:
        my_thread.start()

    results = []
    for each_thread in threads:
        each_thread.join()
        result = each_thread.get_result()
        if len(result) > 0:
            results.extend(result)
    return results


def export_member_to_excel(workbook, race_cid, race_title, today_code, province_code, yesterday):
    """
    会员信息导入
    :param workbook:
    :param race_cid:
    :param race_title:
    :param today_code:
    :return:
    """
    exportedMemberList = statistic_member_info(race_cid, province_code, yesterday)
    print(len(exportedMemberList))
    sheet = workbook.add_worksheet("会员信息")
    sheet.write_string(0, 0, '昵称')
    sheet.write_string(0, 1, 'open_id')
    sheet.write_string(0, 2, '城市')
    sheet.write_string(0, 3, '区县')
    sheet.write_string(0, 4, '手机号码')
    sheet.write_string(0, 5, '答题次数')
    sheet.write_string(0, 6, '当前关卡数')
    sheet.write_string(0, 7, '第一次进入小程序时间')
    sheet.write_string(0, 8, '领取红包数')
    sheet.write_string(0, 9, '领取红包金额')

    for index, member_info in enumerate(exportedMemberList):
        sheet.write_string(index + 1, 0, member_info.nick if member_info.nick else '')
        sheet.write_string(index + 1, 1, member_info.open_id if member_info.open_id else '')
        sheet.write_string(index + 1, 2, member_info.city if member_info.city else '')
        sheet.write_string(index + 1, 3, member_info.district if member_info.district else '')
        sheet.write_string(index + 1, 4, member_info.mobile if member_info.mobile else '')
        sheet.write_number(index + 1, 5, member_info.answerTimes)
        sheet.write_string(index + 1, 6, member_info.currentCheckPoint)
        sheet.write_string(index + 1, 7, member_info.firstTimeOfEnroll.strftime("%Y-%m-%d %H:%M"))
        sheet.write_number(index + 1, 8, member_info.totalNumOfRedPacket)
        sheet.write_number(index + 1, 9, member_info.totalAmountOfRedPacket)
        # sheet.write_string(index + 1, 9, member_info.member_cid)
        # sheet.write_string(index + 1, 10, member_info.open_id)

    # 活动总计信息统计
    export_race_statistic_info(workbook, race_cid, race_title, today_code, exportedMemberList)


def export_race_statistic_info(workbook, race_cid, race_title, today_code, exported_member_infos):
    """
    1.统计到当天为止活动会员总人数、答题总数、红包总数、红包总金额，并存到中间表Race_Statistic_Info
    2.统计与前一天新增数并导出excel
    """
    race_statistic_info = RaceStatisticInfo.sync_find_one({'race_cid': race_cid, 'daily_code': today_code})
    if race_statistic_info is None:
        race_statistic_info = RaceStatisticInfo()
        race_statistic_info.race_cid = race_cid
        race_statistic_info.daily_code = today_code
    # 总计
    race_statistic_info.total_member_count = len(exported_member_infos)
    answer_times = 0
    red_packet_count = 0
    red_packet_amount = 0
    for exported_member in exported_member_infos:
        answer_times += exported_member.answerTimes
        red_packet_count += exported_member.totalNumOfRedPacket
        red_packet_amount += exported_member.totalAmountOfRedPacket
    race_statistic_info.total_answer_times = answer_times
    race_statistic_info.total_red_packet_count = red_packet_count
    race_statistic_info.total_red_packet_amount = red_packet_amount

    history_info_list = RaceStatisticInfo.sync_find(
        {'race_cid': race_cid, 'daily_code': {'$lt': today_code}}).sort([('daily_code', ASC)]).to_list(None)

    pre_total_member_count = 0
    pre_total_answer_times = 0
    pre_total_red_packet_count = 0
    pre_total_red_packet_amount = 0
    if history_info_list:
        pre_total_member_count = history_info_list[-1].total_member_count
        pre_total_answer_times = history_info_list[-1].total_answer_times
        pre_total_red_packet_count = history_info_list[-1].total_red_packet_count
        pre_total_red_packet_amount = history_info_list[-1].total_red_packet_amount
    race_statistic_info.add_member_count = race_statistic_info.total_member_count - pre_total_member_count
    race_statistic_info.add_answer_times = race_statistic_info.total_answer_times - pre_total_answer_times
    race_statistic_info.add_red_packet_count = race_statistic_info.total_red_packet_count - pre_total_red_packet_count
    race_statistic_info.add_red_packet_amount = race_statistic_info.total_red_packet_amount - pre_total_red_packet_amount

    sheet = workbook.add_worksheet("新增信息".format(race_title))
    sheet.write_string(0, 0, '日期')
    sheet.write_string(0, 1, '新增会员数')
    sheet.write_string(0, 2, '新增答题数')
    sheet.write_string(0, 3, '新增红包领取数')
    sheet.write_string(0, 4, '新增红包领取金额')
    sheet.write_string(0, 5, '总会员数')
    sheet.write_string(0, 6, '总答题数')
    sheet.write_string(0, 7, '总红包领取数')
    sheet.write_string(0, 8, '总红包领取金额')
    row = 1
    for index, info in enumerate(history_info_list):
        sheet.write_string(row, 0, info.daily_code)
        sheet.write_number(row, 1,
                           info.add_member_count)
        sheet.write_number(row, 2,
                           info.add_answer_times)
        sheet.write_number(row, 3,
                           info.add_red_packet_count)
        sheet.write_number(row, 4,
                           info.add_red_packet_amount)

        sheet.write_number(row, 5, info.total_member_count)
        sheet.write_number(row, 6, info.total_answer_times)
        sheet.write_number(row, 7, info.total_red_packet_count)
        sheet.write_number(row, 8, info.total_red_packet_amount)
        row += 1
    # 今日新增输出
    sheet.write_string(row, 0, race_statistic_info.daily_code)
    sheet.write_number(row, 1, race_statistic_info.add_member_count)
    sheet.write_number(row, 2, race_statistic_info.add_answer_times)
    sheet.write_number(row, 3, race_statistic_info.add_red_packet_count)
    sheet.write_number(row, 4, race_statistic_info.add_red_packet_amount)

    sheet.write_number(row, 5, race_statistic_info.total_member_count)
    sheet.write_number(row, 6, race_statistic_info.total_answer_times)
    sheet.write_number(row, 7, race_statistic_info.total_red_packet_count)
    sheet.write_number(row, 8, race_statistic_info.total_red_packet_amount)
    race_statistic_info.sync_save()

def update_race_statistic_info(race_cid, today_code, exported_member_infos):
    race_statistic_info = RaceStatisticInfo.sync_find_one({'race_cid': race_cid, 'daily_code': today_code})
    if race_statistic_info is None:
        race_statistic_info = RaceStatisticInfo()
        race_statistic_info.race_cid = race_cid
        race_statistic_info.daily_code = today_code
    # 总计
    race_statistic_info.total_member_count = len(exported_member_infos)
    answer_times = 0
    red_packet_count = 0
    red_packet_amount = 0
    for exported_member in exported_member_infos:
        answer_times += exported_member.answerTimes
        red_packet_count += exported_member.totalNumOfRedPacket
        red_packet_amount += exported_member.totalAmountOfRedPacket
    race_statistic_info.total_answer_times = answer_times
    race_statistic_info.total_red_packet_count = red_packet_count
    race_statistic_info.total_red_packet_amount = red_packet_amount

    history_info_list = RaceStatisticInfo.sync_find(
        {'race_cid': race_cid, 'daily_code': {'$lt': today_code}}).sort([('daily_code', ASC)]).to_list(None)

    pre_total_member_count = 0
    pre_total_answer_times = 0
    pre_total_red_packet_count = 0
    pre_total_red_packet_amount = 0
    if history_info_list:
        pre_total_member_count = history_info_list[-1].total_member_count
        pre_total_answer_times = history_info_list[-1].total_answer_times
        pre_total_red_packet_count = history_info_list[-1].total_red_packet_count
        pre_total_red_packet_amount = history_info_list[-1].total_red_packet_amount
    race_statistic_info.add_member_count = race_statistic_info.total_member_count - pre_total_member_count
    race_statistic_info.add_answer_times = race_statistic_info.total_answer_times - pre_total_answer_times
    race_statistic_info.add_red_packet_count = race_statistic_info.total_red_packet_count - pre_total_red_packet_count
    race_statistic_info.add_red_packet_amount = race_statistic_info.total_red_packet_amount - pre_total_red_packet_amount

    race_statistic_info.sync_save()

def export_all_race_member():
    today = datetime.now()
    today_code = format(today, "%Y-%m-%d")
    yesterday = today.replace(hour=0, minute=0, second=0, microsecond=0)
    race_cursor = Race.sync_find({'status': 1})
    for race in race_cursor:
        # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
        # 安徽 3040737C97F7C7669B04BC39A660065D
        if race.cid == 'CA755167DEA9AA89650D11C10FAA5413':
            print('Start', race.title)
            workbook = xlsxwriter.Workbook('{}_会员信息_{}.xlsx'.format(race.title, today_code))
            export_member_to_excel(workbook, race.cid, race.title, today_code, race.province_code, yesterday)
            workbook.close()


def transform_date(time_str):
    """
    将时间字符串转换成日期 20190627转换成Date(20190627)
    :param time_str:
    :return:
    """
    date = time_str[:4] + '/' + time_str[4:6] + '/' + time_str[6:]
    date = date.replace("/0", "/")
    return str2datetime(date, "%Y/%m/%d")


def test2():
    daily_code = '2019-07-08'
    today = transform_date('20190710')
    yesterday = today.replace(hour=0, minute=0, second=0, microsecond=0)
    print(yesterday)
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D
    info = RaceStatisticInfo.sync_find_one(
        {'race_cid': 'CA755167DEA9AA89650D11C10FAA5413', 'daily_code': '2019-07-10'})
    print("处理前总数", info.daily_code, '人数', info.total_member_count, '答题数', info.total_answer_times, '红包',
          info.total_red_packet_count, '金额', info.total_red_packet_amount)
    print("处理前新增", info.daily_code, '人数', info.add_member_count, '答题数', info.add_answer_times, '红包',
          info.add_red_packet_count, '金额', info.add_red_packet_amount)
    race = Race.sync_find_one({'cid': info.race_cid})
    exportedMemberList = statistic_member_info(race.cid, race.province_code, yesterday)
    update_race_statistic_info(race.cid,daily_code,exportedMemberList)
    member_count = len(exportedMemberList)
    answer_times = 0
    red_packet_count = 0
    red_packet_amount = 0
    for exported_member in exportedMemberList:
        answer_times += exported_member.answerTimes
        red_packet_count += exported_member.totalNumOfRedPacket
        red_packet_amount += exported_member.totalAmountOfRedPacket
    print("8号之前:",'人数',member_count,'答题数',answer_times,'红包',red_packet_count,'金额',red_packet_amount)
    info.add_member_count = info.total_member_count - member_count
    info.add_answer_times = info.total_answer_times - answer_times
    info.add_red_packet_count = info.total_red_packet_count - red_packet_count
    info.add_red_packet_amount = info.total_red_packet_amount - red_packet_amount

    print("处理后总数", info.daily_code, '人数', info.total_member_count, '答题数', info.total_answer_times, '红包',
          info.total_red_packet_count, '金额', info.total_red_packet_amount)
    print("处理后新增", info.daily_code, '人数', info.add_member_count, '答题数', info.add_answer_times, '红包',
          info.add_red_packet_count, '金额', info.add_red_packet_amount)
    # info.sync_save()


def test(today_code):
    # 六安 CA755167DEA9AA89650D11C10FAA5413 贵州 F742E0C7CA5F7E175844478D74484C29
    # 安徽 3040737C97F7C7669B04BC39A660065D
    history_info_list = RaceStatisticInfo.sync_find(
        {'race_cid': 'CA755167DEA9AA89650D11C10FAA5413', 'daily_code': {'$lte': today_code}}).sort(
        [('daily_code', ASC)]).to_list(None)
    # history_info_list = RaceStatisticInfo.sync_find().sort(
    #     [('daily_code', ASC)]).to_list(None)
    len(history_info_list)
    for info in history_info_list:
        print(info.race_cid)
        print("111总数", info.daily_code, '人数', info.total_member_count, '答题数', info.total_answer_times, '红包',
              info.total_red_packet_count, '金额', info.total_red_packet_amount)
        print("111新增", info.daily_code, '人数', info.add_member_count, '答题数', info.add_answer_times, '红包',
              info.add_red_packet_count, '金额', info.add_red_packet_amount)

def test3():
    cursor = RaceMapping.sync_aggregate([
        MatchStage(
            {'race_cid': "CA755167DEA9AA89650D11C10FAA5413",
             'member_cid':'9809FD6ED3F9534F87252A48018BE965','auth_address.province': {'$ne': None}, "record_flag": 1,}),
        GroupStage({'member_cid': '$member_cid'}, race_list={'$push': '$$ROOT'}),
        LookupStage(Member, '_id.member_cid', 'cid', 'member_list'),
        MatchStage({'member_list': {'$ne': []}})
    ], allowDiskUse=True)
    for race_member in cursor:
        print(len(race_member.race_list))
        for race in race_member.race_list:
            print(race.cid,'---',race.mobile)

def test4():
    today_code = '2019-07-10'
    info = RaceStatisticInfo.sync_find_one(
        {'race_cid': 'CA755167DEA9AA89650D11C10FAA5413', 'daily_code': today_code})
    info.total_answer_times = 73474
    info.total_red_packet_count = 1389
    info.total_red_packet_amount = 916.74
    info.add_answer_times = 14511
    info.add_red_packet_count = 212
    info.add_red_packet_amount = 129.44
    info.sync_save()
    test(today_code)

if __name__ == "__main__":
    # race = Race.sync_find_one({'cid': "3040737C97F7C7669B04BC39A660065D"})
    # print('Start', race.title)
    today = datetime.now()
    today_code = format(today, "%Y-%m-%d")
    # workbook = xlsxwriter.Workbook('会员信息{}.xlsx'.format(today_code))
    # 会员信息
    # export_member_to_excel(workbook, race.cid, race.title, today_code,race.province_code)
    export_all_race_member()
    # test(today_code)
    # test2()
    #test4()

