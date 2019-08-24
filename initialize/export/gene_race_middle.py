#   导入该活动的累计参与人数，参与人次，新增人数，新增人次，通关人数，红包领取情况
import datetime

from commons.common_utils import datetime2str
from db.models import Race, AdministrativeDivision, Member, MemberStatisticInfo, RaceMemberEnterInfoStatistic
from logger import log_utils
from motorengine.stages import MatchStage, LookupStage, GroupStage

today = format(datetime.datetime.now(), "%Y-%m-%d%H:%M")


def generate_all_middle_data():
    """
    生成全部的中间表数据
    :return:
    """
    race_cid_list = ["CA755167DEA9AA89650D11C10FAA5413", "3040737C97F7C7669B04BC39A660065D",
                     "F742E0C7CA5F7E175844478D74484C29", "DF1EDC30F120AEE93351A005DC97B5C1"]
    # race_cid_list = ["3040737C97F7C7669B04BC39A660065D"]
    for cid in race_cid_list:
        RaceMemberEnterInfoStatistic.sync_delete_many({'race_cid': cid})
        generate_race_middle(cid, 'total')


def generate_race_middle(race_cid: str, start):
    """
    生成中间表
    :return:
    """
    if not isinstance(race_cid, str):
        raise ValueError("race_cid is not str")
    prov_match = MatchStage({'province': {'$ne': None}})
    race = Race.sync_get_by_cid(race_cid)
    #  市级活动，如六安市，扬州市
    if race.city_code:
        city_code_list = AdministrativeDivision.sync_distinct('code', {'code': race.city_code})
        #  该活动的所属城市范围
        city_name_list = AdministrativeDivision.sync_distinct('title', {'code': race.city_code})
    else:
        prov = AdministrativeDivision.sync_find_one({'code': race.province_code})
        city_code_list = AdministrativeDivision.sync_distinct('code', {'parent_code': race.province_code})
        city_name_list = AdministrativeDivision.sync_distinct('title', {'parent_code': race.province_code})
        prov_match = MatchStage({'province': prov.title})
    dist_list = []
    for city_code in city_code_list:
        #  该活动区县的范围
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city_code})
    lookup_stage = LookupStage(Member, 'member_cid', 'cid', 'member_list')
    has_town_match = {'race_cid': race_cid, 'city': {'$in': city_name_list}, 'district': {'$in': dist_list},
                      'member_cid': {'$ne': None}, 'town': {'$ne': None}}

    no_town_match = {'race_cid': race_cid, 'city': {'$in': city_name_list}, 'district': {'$in': dist_list},
                     'member_cid': {'$ne': None}, 'town': {'$eq': None}}
    if start != "total":
        start_time = transform_time_format(start)
        end_time = transform_time_format(start + datetime.timedelta(days=1))
        has_town_match['daily_code'] = {'$gte': start_time, '$lt': end_time}
        no_town_match['daily_code'] = {'$gte': start_time, '$lt': end_time}
    cursor = MemberStatisticInfo.sync_aggregate(
        [
            MatchStage(has_town_match),
            lookup_stage,
            prov_match,
            MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {"daily_code": "$daily_code", 'district': '$district', 'city': '$city', 'town': '$town'},
                province={"$first": "$province"}, town={"$last": "$town"},
                status_list={'$push': '$is_new_user'}, pass_status_list={'$push': '$is_final_passed'},
                enter_times={'$sum': "$enter_times"}, count_sum={'$sum': "$grant_red_packet_count"},
                amount_sum={'$sum': "$grant_red_packet_amount"},
                receive_count_sum={'$sum': "$draw_red_packet_count"},
                receive_amount_sum={'$sum': "$draw_red_packet_amount"},
                answer_times={'$sum': '$answer_times'},
                true_answer_times={'$sum': '$true_answer_times'},
                sum={'$sum': 1}),
        ]
    )
    no_town_cursor = MemberStatisticInfo.sync_aggregate(
        [
            MatchStage(no_town_match),
            lookup_stage,
            prov_match,
            MatchStage({'member_list': {'$ne': []}}),
            GroupStage(
                {"daily_code": "$daily_code", 'district': '$district', 'city': '$city'},
                province={"$first": "$province"}, town={"$last": "$town"},
                status_list={'$push': '$is_new_user'}, pass_status_list={'$push': '$is_final_passed'},
                enter_times={'$sum': "$enter_times"}, count_sum={'$sum': "$grant_red_packet_count"},
                amount_sum={'$sum': "$grant_red_packet_amount"},
                receive_count_sum={'$sum': "$draw_red_packet_count"},
                receive_amount_sum={'$sum': "$draw_red_packet_amount"},
                answer_times={'$sum': '$answer_times'},
                true_answer_times={'$sum': '$true_answer_times'},
                sum={'$sum': 1}),
        ]
    )
    while True:
        try:
            race_member_info = cursor.next()
            daily_code = race_member_info.id.get('daily_code')
            status_list = race_member_info.status_list
            pass_status_list = race_member_info.pass_status_list
            district = race_member_info.id.get('district')
            city = race_member_info.id.get('city')
            if district and city:
                race_enter_info = RaceMemberEnterInfoStatistic(daily_code=daily_code, race_cid=race_cid)
                race_enter_info.province = race_member_info.province
                race_enter_info.city = city
                race_enter_info.district = district
                race_enter_info.town = race_member_info.town
                race_enter_info.company_cid = race_member_info.company_cid if race_member_info.company_cid else None
                race_enter_info.company_name = race_member_info.company_name if race_member_info.company_name else None
                race_enter_info.increase_enter_count = status_list.count(1)  # 每日新增
                race_enter_info.enter_count = race_member_info.sum  # 每日参与
                race_enter_info.pass_count = pass_status_list.count(1)  # 每日通关人数
                race_enter_info.enter_times = race_member_info.enter_times  # 每日参与次数
                race_enter_info.grant_red_packet_count = race_member_info.count_sum  # 红包发放数量
                race_enter_info.grant_red_packet_amount = race_member_info.amount_sum  # 红包发放金额
                race_enter_info.draw_red_packet_count = race_member_info.receive_count_sum  # 红包领取数量
                race_enter_info.draw_red_packet_amount = race_member_info.receive_amount_sum  # 红包领取金额
                race_enter_info.correct_percent = round(
                    race_member_info.true_answer_times / race_member_info.answer_times,
                    2) if race_member_info.answer_times != 0 else 0
                race_enter_info.answer_times = race_member_info.answer_times  # 总答题数量
                race_enter_info.true_answer_times = race_member_info.true_answer_times  # 总答对题目数量
                race_enter_info.sync_save()
            else:
                continue
        except StopIteration:
            break
        except Exception as e:
            raise e

    while True:
        try:
            race_member_info = no_town_cursor.next()
            daily_code = race_member_info.id.get('daily_code')
            status_list = race_member_info.status_list
            pass_status_list = race_member_info.pass_status_list
            district = race_member_info.id.get('district')
            city = race_member_info.id.get('city')
            if district and city:
                race_enter_info = RaceMemberEnterInfoStatistic(daily_code=daily_code, race_cid=race_cid)
                race_enter_info.province = race_member_info.province
                race_enter_info.city = city
                race_enter_info.district = district
                race_enter_info.company_cid = race_member_info.company_cid if race_member_info.company_cid else None
                race_enter_info.company_name = race_member_info.company_name if race_member_info.company_name else None
                race_enter_info.increase_enter_count = status_list.count(1)  # 每日新增
                race_enter_info.enter_count = race_member_info.sum  # 每日参与
                race_enter_info.pass_count = pass_status_list.count(1)  # 每日通关人数
                race_enter_info.enter_times = race_member_info.enter_times  # 每日参与次数
                race_enter_info.grant_red_packet_count = race_member_info.count_sum  # 红包发放数量
                race_enter_info.grant_red_packet_amount = race_member_info.amount_sum  # 红包发放金额
                race_enter_info.draw_red_packet_count = race_member_info.receive_count_sum  # 红包领取数量
                race_enter_info.draw_red_packet_amount = race_member_info.receive_amount_sum  # 红包领取金额
                race_enter_info.correct_percent = round(
                    race_member_info.true_answer_times / race_member_info.answer_times,
                    2) if race_member_info.answer_times != 0 else 0  # 正确率
                race_enter_info.answer_times = race_member_info.answer_times  # 总答题数量
                race_enter_info.true_answer_times = race_member_info.true_answer_times  # 总答对题目数量
                race_enter_info.sync_save()
            else:
                continue
        except StopIteration:
            break
        except Exception as e:
            raise e


def delete_data(race_cid):
    race_info = RaceMemberEnterInfoStatistic.sync_find({'race_cid': race_cid})
    for i in race_info:
        i.sync_delete()


def transform_time_format(export_dt):
    """
    把时间日期格式得数据转换成指定得字符串形式
    :param export_dt:
    :return:
    """
    time_str = datetime2str(export_dt, date_format='%Y%m%d')
    return time_str


logger = log_utils.get_logging('member_stat_schedule', 'member_stat_schedule.log')


def generate_total(export_time):
    race_cid_list = Race.sync_distinct('cid', {'status': 1})
    for cid in race_cid_list:
        if cid == '160631F26D00F7A2DC56DAE2A0C4AF12':
            continue
        RaceMemberEnterInfoStatistic.sync_delete_many(
            {'race_cid': cid, 'daily_code': transform_time_format(export_time)})
        generate_race_middle(cid, export_time)


if __name__ == '__main__':
    # generate_race_middle("CA755167DEA9AA89650D11C10FAA5413", datetime.datetime.now() + datetime.timedelta(days=-6))
    generate_all_middle_data()
    pass
