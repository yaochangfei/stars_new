# !/usr/bin/python
# -*- coding:utf-8 -*-


from datetime import datetime
import threading

import xlsxwriter

from db.models import RaceMapping, Member, MemberCheckPointHistory, RaceGameCheckPoint, RedPacketBox, Race, BaseModel, \
    AdministrativeDivision
from motorengine import StringField, DESC, ReadPreference
from motorengine.fields import IntegerField, FloatField
from motorengine.stages import GroupStage, MatchStage, ProjectStage


class RaceStatisticInfo(BaseModel):
    race_cid = StringField(required=True)  # 竞赛活动cid信息
    daily_code = StringField(required=True)  # 日期
    total_member_count = IntegerField(default=0)  # 总会员人数
    total_answer_times = IntegerField(default=0)  # 总答题数
    total_red_packet_count = IntegerField(default=0)  # 总红包数
    total_red_packet_amount = FloatField(default=0.0)  # 总红包金额


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


def get_member_info(thread_index, memberCidList, race_cid, checkPointCidList, lastCheckPoint, checkPointMap):
    print(thread_index, "号线程开始处理")
    # print(memberCidList)
    exportedMemberList = []
    for memberCid in memberCidList:
        member = Member.sync_find_one({'cid': memberCid})
        if member is None:
            print("未找到member_cid:{}的基础信息".format(memberCid))
            continue
        raceMapping = RaceMapping.sync_find_one(
            {'race_cid': race_cid, 'member_cid': memberCid, 'record_flag': 1, 'auth_address.province': {'$ne': None}})
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
            exportedMember.mobile = ''
        else:
            exportedMember.mobile = mobile
        check_point_cid = getattr(raceMapping, 'race_check_point_cid', None)
        if check_point_cid is None:
            exportedMember.currentCheckPoint = "1"
        elif check_point_cid == lastCheckPoint:
            exportedMember.currentCheckPoint = "已通关"
        else:
            exportedMember.currentCheckPoint = checkPointMap[check_point_cid]
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
        print(thread_index, member.cid, exportedMember.nick, exportedMember.city, exportedMember.district,
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
    race_member_match = {"race_cid": race_cid, 'record_flag': 1, 'auth_address.province': {'$ne': None},
                         'auth_address.city': {"$in": city_name_list},
                         'auth_address.district': {"$in": district_name_list},
                         'created_dt': {'$lte': yesterday}}
    match = {"race_cid": race_cid, 'record_flag': 1}
    # 当前活动参与会员
    memberCidList = RaceMapping.sync_distinct("member_cid", race_member_match)
    memberCidList.sort()
    # 当前活动关卡cid
    checkPointList = RaceGameCheckPoint.sync_aggregate([MatchStage(match)])
    checkPointMap = {}
    lastCheckPoint = None
    maxCheckPointIndex = 0
    for check_point in checkPointList:
        checkPointMap[check_point.cid] = check_point.alias
        if check_point.index > maxCheckPointIndex:
            maxCheckPointIndex = check_point.index
            lastCheckPoint = check_point.cid
    checkPointCidList = list(checkPointMap.keys())

    # print("该活动下的会员", len(memberCidList), memberCidList)
    # print("该活动下的会员数", len(set(memberCidList)))
    # print("该活动下的关卡", len(checkPointCidList), checkPointCidList)

    temp_list = splitList(memberCidList, 2000)
    threads = []
    thread_num = 1
    for my_list in temp_list:
        # print(my_list)
        t = MyThread(get_member_info,
                     args=(thread_num, my_list, race_cid, checkPointCidList, lastCheckPoint, checkPointMap))
        threads.append(t)
        t.start()
        thread_num += 1

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
    sheet.write_string(0, 1, '城市')
    sheet.write_string(0, 2, '区县')
    sheet.write_string(0, 3, '手机号码')
    sheet.write_string(0, 4, '答题次数')
    sheet.write_string(0, 5, '当前关卡数')
    sheet.write_string(0, 6, '第一次进入小程序时间')
    sheet.write_string(0, 7, '领取红包数')
    sheet.write_string(0, 8, '领取红包金额')

    for index, member_info in enumerate(exportedMemberList):
        sheet.write_string(index + 1, 0, member_info.nick if member_info.nick else '')
        sheet.write_string(index + 1, 1, member_info.city if member_info.city else '')
        sheet.write_string(index + 1, 2, member_info.district if member_info.district else '')
        sheet.write_string(index + 1, 3, member_info.mobile if member_info.mobile else '')
        sheet.write_number(index + 1, 4, member_info.answerTimes)
        sheet.write_string(index + 1, 5, member_info.currentCheckPoint)
        sheet.write_string(index + 1, 6, member_info.firstTimeOfEnroll.strftime("%Y-%m-%dT%H:%M"))
        sheet.write_number(index + 1, 7, member_info.totalNumOfRedPacket)
        sheet.write_number(index + 1, 8, member_info.totalAmountOfRedPacket)
        # sheet.write_string(index + 1, 9, member_info.member_cid)
        # sheet.write_string(index + 1, 10, member_info.open_id)

    # 活动总计信息统计
    export_race_statistic_info(workbook, race_cid, race_title, today_code, exportedMemberList)


def export_race_statistic_info(workbook, race_cid, race_title, today_code, exported_member_infos):
    """
    1.统计到当天为止活动会员总人数、答题总数、红包总数、红包总金额，并存到中间表Race_Statistic_Info
    2.统计与前一天新增数并导出excel
    """
    race_statistic_info = RaceStatisticInfo()
    race_statistic_info.race_cid = race_cid
    race_statistic_info.daily_code = today_code
    race_statistic_info.total_member_count = len(exported_member_infos)
    for exported_member in exported_member_infos:
        race_statistic_info.total_answer_times += exported_member.answerTimes
        race_statistic_info.total_red_packet_count += exported_member.totalNumOfRedPacket
        race_statistic_info.total_red_packet_amount += exported_member.totalAmountOfRedPacket

    pre_cusor = RaceStatisticInfo.sync_find_one(
        {'race_cid': race_cid, 'daily_code': {'$ne': today_code}})
    pre_total_member_count = 0
    pre_total_answer_times = 0
    pre_total_red_packet_count = 0
    pre_total_red_packet_amount = 0
    if pre_cusor:
        # pre_race_statistic_info = pre_cusor.sort(['daily_code', DESC]).limit(1)
        # if pre_cusor:
        pre_total_member_count = pre_cusor.total_member_count
        pre_total_answer_times = pre_cusor.total_answer_times
        pre_total_red_packet_count = pre_cusor.total_red_packet_count
        pre_total_red_packet_amount = pre_cusor.total_red_packet_amount

    sheet = workbook.add_worksheet("新增信息".format(race_title))
    sheet.write_string(0, 0, '新增会员数')
    sheet.write_string(0, 1, '新增答题数')
    sheet.write_string(0, 2, '新增红包领取数')
    sheet.write_string(0, 3, '新增红包领取金额数')
    sheet.write_number(1, 0, race_statistic_info.total_member_count - pre_total_member_count)
    sheet.write_number(1, 1, race_statistic_info.total_answer_times - pre_total_answer_times)
    sheet.write_number(1, 2, race_statistic_info.total_red_packet_count - pre_total_red_packet_count)
    sheet.write_number(1, 3, race_statistic_info.total_red_packet_amount - pre_total_red_packet_amount)

    race_statistic_info.sync_save()


def export_all_race_member():
    today = datetime.now()
    today_code = format(today, "%Y-%m-%d")
    yesterday = today.replace(hour=0, minute=0, second=0, microsecond=0)
    race_cursor = Race.sync_find()
    for race in race_cursor:
        print('Start', race.title)
        workbook = xlsxwriter.Workbook('{}{}.xlsx'.format(race.title, today_code))
        export_member_to_excel(workbook, race.cid, race.title, today_code, race.province_code, yesterday)
        workbook.close()


if __name__ == "__main__":
    # race = Race.sync_find_one({'cid': "3040737C97F7C7669B04BC39A660065D"})
    # print('Start', race.title)
    # today = datetime.now()
    # today_code = format(today, "%Y-%m-%d")
    # workbook = xlsxwriter.Workbook('会员信息{}.xlsx'.format(today_code))
    # 会员信息
    # export_member_to_excel(workbook, race.cid, race.title, today_code,race.province_code)
    export_all_race_member()
