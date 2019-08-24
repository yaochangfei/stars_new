#  测试
# import datetime
#
# from db.models import ReportRacePeopleStatistics, RaceMapping, MemberCheckPointHistory, RaceGameCheckPoint
# from motorengine import ASC
# from motorengine.stages import MatchStage, GroupStage, SortStage
#
# # race_cid = "CA755167DEA9AA89650D11C10FAA5413"
# # district_title_list = ['舒城县', '叶集区', '霍邱县', '金安区', '裕安区', '金寨县', '开发区', '霍山县']
# # count_match = {'race_cid': race_cid,
# #                    "city": "六安市",
# #                    'district': {'$in': district_title_list}, 'town': {'$ne': None}}
# # match_stage = MatchStage(count_match)
# # group_stage = GroupStage(
# #     {'daily_code': '$daily_code', 'province': '$province', 'city': '$city', "district": "$district",
# #      'town': '$town'}, sum={'$sum': '$total_num'})
# # sort_stage = SortStage([('_id.daily_code', ASC)])
# # address_group = GroupStage({'province': '$province', 'city': '$city', "district": "$district", 'town': '$town'},
# #                                sum={'$sum': '$total_num'})
# # address_sort = SortStage([('_id.district', ASC), ('_id.town', ASC)])
# # address_list = ReportRacePeopleStatistics.sync_find({'race_cid': race_cid, 'record_flag': 1, 'town': {'$ne': None}}).to_list(None)
# # print(address_list)
# # print(len(address_list))
# # print('---------------')
# # company_list = ReportRacePeopleStatistics.sync_find({'race_cid': race_cid, 'record_flag': 1, 'company_cid': {'$ne': None}}).to_list(None)
# # print(company_list)
# # print(len(company_list))
# #
# # # for index, address in enumerate(address_list):
# # #     city = address.id.get('city')
# # #     print(city)
# # #     district = address.id.get('district')
# # #     print(district)
# # #     town = address.id.get('town')
# # #     print(town)
# # #     if not town:
# # #         continue
# #
# # print('++++++++++++++++++++')
# # address_list1 = RaceMapping.sync_find({'race_cid': race_cid, 'record_flag': 1, 'town': {'$ne': None}}).to_list(None)
# # print(address_list1)
# # print(len(address_list1))
# # print('---------------')
# # company_list1 = RaceMapping.sync_find({'race_cid': race_cid, 'record_flag': 1, 'company_cid': {'$ne': None}}).to_list(None)
# # print(company_list1)
# # print(len(company_list1))
# # print('*********************')
# # member_list = MemberCheckPointHistory.sync_distinct("member_cid", {'check_point_cid': "AFC97D7D354C1D44BF64A5DDAB76E8D7", 'status': 1})
# # print(len(member_list))
# # num = 0
# # for i in member_list:
# #     race_mapping = RaceMapping.sync_find_one({'race_cid': race_cid, 'member_cid': i})
# #     if race_mapping:
# #         print('yes')
# #         num += 1
# #     else:
# #         print('no')
# #
# # print(num)
# #
# # print('11111111111111')
# # import datetime
# now = datetime.datetime.now()
# #  六月3号
# yes_day = now.replace(hour=10, minute=0, second=0, microsecond=0)
# print(yes_day, 'day1')
#
# member_list = RaceMapping.sync_distinct('member_cid',{"race_cid": "3040737C97F7C7669B04BC39A660065D", 'auth_address.district': '叶集区',"updated_dt": {'$lt': yes_day}})
# print(len(member_list))
# member_list1 = RaceMapping.sync_distinct('member_cid',{"race_cid": "3040737C97F7C7669B04BC39A660065D", 'auth_address.district': '叶集区',"updated_dt": {'$lt': yes_day}})
# print(len(member_list1))
# # tom_day = yes_day + datetime.timedelta(days=1)
# # print(yes_day, 'day')
# # member_list = RaceMapping.sync_distinct('member_cid',{"race_cid": "3040737C97F7C7669B04BC39A660065D", "updated_dt": {'$gt': yes_day, '$lt': tom_day}})
# # print(len(member_list))
# # check_point_list = RaceGameCheckPoint.sync_find({'race_cid': "3040737C97F7C7669B04BC39A660065D"})
# # cid_lsit = [check_point.cid for check_point in check_point_list]
# # his_list = MemberCheckPointHistory.sync_find({'check_point_cid': {'$in': cid_lsit}, "updated_dt":{'$gt': yes_day, '$lt': tom_day}}).to_list(None)
# # print(len(his_list), '999999')
#
# #  测试通关的
# city_history_list = MemberCheckPointHistory.sync_distinct("member_cid", {'check_point_cid': "AFC97D7D354C1D44BF64A5DDAB76E8D7", 'status': 1})
# race_mapping_list = RaceMapping.sync_distinct("member_cid", {'race_cid': 'CA755167DEA9AA89650D11C10FAA5413', "auth_address.city"})
# print(len(city_history_list))
# prov_history_list = MemberCheckPointHistory.sync_distinct("member_cid", {'check_point_cid': "05528C744EE42E838F7EE9D69070E6AA", 'status': 1})
# print(len(prov_history_list))
import datetime
import random

from db.models import AdministrativeDivision, RaceMapping, MemberCheckPointHistory, Member, Race

district_title_list = AdministrativeDivision.sync_distinct('title', {'parent_code': "341500"})

# match = {"race_cid": "3040737C97F7C7669B04BC39A660065D", "auth_address.city": "六安市", "auth_address.province": {'$ne': None},"auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}}
# city_match = {"race_cid": "CA755167DEA9AA89650D11C10FAA5413", "auth_address.city": "六安市","auth_address.province": {'$ne': None},"auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}}
#
# member_list = RaceMapping.sync_distinct("member_cid", match)
# print(len(member_list))
#
# city_member_list = RaceMapping.sync_distinct("member_cid", city_match)
# print(len(city_member_list))
# total_list = []
# total_list += member_list
# total_list += city_member_list
# print(len(list(total_list)))



# now = datetime.datetime.now()
# yes_day = (now + datetime.timedelta(days=-6)).replace(hour=0)
# tom = (now + datetime.timedelta(days=-5)).replace(hour=0)
# print(yes_day)
# time_match = {"race_cid": "3040737C97F7C7669B04BC39A660065D", "auth_address.city": "六安市", "auth_address.province": {'$ne': None},"auth_address.district": {'$in': ['金寨县']}, "created_dt": {"$gt": yes_day, "$lt": tom}}
# member_list2 = RaceMapping.sync_distinct("member_cid", time_match)
# print(member_list2)
# print(len(member_list2))
# cid_list = ['F21192604292671939F60D29656A70FB', 'A9E53CE409EB4FF59A089DB1E2E3E889', 'ABBDF83AC88172D621EFF570433B144A', '39DF4B1996B8C77DE159AA3C8A5013BA', '2907A57A81595DC41357360B037402A3', '8A1C326884A6E831C50443EBC56DB37D', 'D3D9C418911A0925280454CFC81A9443', '83320F49960563B478D3E2AD45F05080', 'C7DA4599B80A3158C4DBE0F5D94F741F', '32625292D538FEE2E56C62C4D72DFC71', 'ECA145841F097B5BCA936192E08992F5', '4830B48FB9608ECE2CF14F23CE2AE45F', 'A40BF4437F928017259B76F968AF4E3D', '5A3F147A6EACE6C8A24197D6E7A4F03F', 'A0EDA9345D30758CB20484FD7DFB652F', 'A28BC8B13DD7FFA0A9102AD10EDCBD8D', '1E8EFF76B93674BAFEBFF70FECA88C5D', '6A2DF3191134E2B27AE52FB4C398948D', 'DC19707A0FCAE5F8044AE2A53B886029', 'EF4F3778A2F83284EC4076B735CD341D', '0E814C87542D93D90B9E8A355FE932E6', '2AAE2D3FEA9A7D3ED028618F5B8D1D58', '2DDB9888CB0DCC98D3112DE1101AF824', 'F208ACD5C20976C6148216AD9BE97018', 'B99397C21F67ADFFC8F677F3F0B29657', '66F023DE4970D4AFBD8BD316C796753C', 'DB2F76E3304C866599E63EDE6DC9545B', '88F2B828189D2D5112B5708FAB85C74D', 'A625B79B807865BF3F266CFB55741272', '91C852E14678FC446AD669B5D138BBCB', 'F4FCE2644AE92EC9E47500E201B552BC', 'A1E590588A5DB6B4FA24212C15AE1FDF', '1FBD8D5501BDC4BC02F48569DC656B7F', '5579B8671D451C90F5921DAC539AC8F8', 'EBEBD61177B2DB81A64212AE24DF2CFE', '88E4E781192A3335A7E789239B7CB9BA', '7A571007812B3A121A72EA2F091BB52D', '44FCB9D8A8A25BFDFD0A2B73ED3EAFFE', '35F27A7B8D068C8B1B2BD0E6C66F32EB', 'FC316B4F8B7F8A14396341F3F0D36E88', '9C42EE5DC5136CD28F7FBAF5CFA9E3A1', 'B288F6188DE277CC7B85AEBB5493B72D', '7087DD480FE4969E32A5AA09AB0C8F46', '7EABA67F59C542559BEC91C633024579', '9319145A8A6BE7DEF66960432525DFFC', 'B8626F57FD60CC4A38960342630CC0FE', '0EC761461183F840EE3E9953D7F2FA91', '8154FDB280121E7EB48FF6C8A950CCD1', '1232707D7C0D084A4432F0EA6627AF0B', '3E180A00CEF5B6472589DB01A1F79849', 'D215585135922DBD32745291C2E3E4F4', '908426FA5CAC5F8A9CF003FD36EA6D2F', '29B2B2662EE3281C0ABD8746B9B7711F']
# time_match2 = {"member_cid": {'$in': cid_list}, "race_cid": "CA755167DEA9AA89650D11C10FAA5413", "auth_address.city": "六安市", "auth_address.province": {'$ne': None},"auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}, "created_dt": {"$lt": yes_day}}
# member_list3 = RaceMapping.sync_distinct("member_cid", time_match2)
# print(member_list3)
#
# prov_pass_list = MemberCheckPointHistory.sync_distinct("member_cid", {"check_point_cid": "05528C744EE42E838F7EE9D69070E6AA", "record_flag": 1, "status": 1})
# print(len(prov_pass_list), 'len5')
#
# race_mapping_list = RaceMapping.sync_distinct("member_cid", {"race_cid": "3040737C97F7C7669B04BC39A660065D", 'member_cid': {'$in': prov_pass_list}, 'auth_address.province': {'$ne': None},'auth_address.city': "六安市", "auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}, "record_flag": 1})
# print(len(race_mapping_list), 'map1')
#
# city_pass_list = MemberCheckPointHistory.sync_distinct("member_cid", {"check_point_cid": "AFC97D7D354C1D44BF64A5DDAB76E8D7", "record_flag": 1, "status": 1})
# print(len(city_pass_list), 'len6')
# print(city_pass_list)
# city_mapping_list = RaceMapping.sync_distinct("member_cid", {"race_cid": "CA755167DEA9AA89650D11C10FAA5413",'member_cid': {'$in': city_pass_list}, 'auth_address.province': {'$ne': None},'auth_address.city': "六安市", "auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}, "record_flag": 1})
#
# print(len(city_mapping_list), 'map2')
# t_list = []
# for i in race_mapping_list:
#     t_list.append(i)
#
# for i in city_mapping_list:
#     t_list.append(i)
# #
# print(len(list(set(t_list))))
#
# map2 = city_mapping_list = RaceMapping.sync_distinct("member_cid", {"race_cid": "CA755167DEA9AA89650D11C10FAA5413",'member_cid': {'$in': city_pass_list}, 'auth_address.province': {'$ne': None}, "auth_address.town": {'$eq': None},'auth_address.city': "六安市", "auth_address.district": {'$in': ['金安区', '裕安区', '叶集区', '霍邱县', '舒城县', '金寨县', '霍山县', '开发区']}, "record_flag": 1})
# print(len(map2))
# for i in map2:
#     if i not in race_mapping_list:
#         race_mapping_list.append(i)
# print(len(race_mapping_list))
# city_map2 = RaceMapping.sync_distinct("member_cid",{'race_cid': "CA755167DEA9AA89650D11C10FAA5413", "member_cid": {'$in': city_pass_list}})
# print(len(city_map2))
from db.models import ReportRacePeopleStatistics
# now = datetime.datetime.now()
# print(now)
# midnight = now.replace(hour=0, minute=0, second=0)
# _yes = now + datetime.timedelta(days=-45)
# list_b = [now + datetime.timedelta(days=-n) for n in range(1, 7)]
# list_b.append(now)
# print(list_b)
# print(midnight)
# _map_list = RaceMapping.sync_find({"auth_address.town": {'$ne': None}, 'race_cid': "CA755167DEA9AA89650D11C10FAA5413"}).to_list(None)
# print(len(_map_list))
# for map in _map_list:
#     map.created_dt = random.choice(list_b)
#     map.updated_dt = random.choice(list_b)
#     map.sync_save()

# print('====================')
# now = datetime.datetime.now()
# yes = (now + datetime.timedelta(days=-7)).replace(hour=0, minute=0, second=0)
# tom = yes + datetime.timedelta(days=1)
# print(yes, 'yes')
# print(tom, 'tom')
# member_cid_list = MemberCheckPointHistory.sync_distinct("member_cid", {'check_point_cid': "AFC97D7D354C1D44BF64A5DDAB76E8D7", 'status': 1, 'record_flag': 1})
# print(len(member_cid_list))
# num = 0
# for cid in member_cid_list:
#     member = Member.sync_find_one({'cid': cid})
#     if member:
#         race_mapping = RaceMapping.sync_find_one({'race_cid': "CA755167DEA9AA89650D11C10FAA5413", 'auth_address.city': '六安市', "member_cid": cid})
#         if race_mapping:
#             num += 1
# print(num)

#     red.sync_save()
from db.models import RaceGameCheckPoint


def check(race_cid:str):
    """
    检查多少人参与活动但是没有答过题目的
    :param race_cid:
    :return:
    """
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
    dist_list = []
    print(city_name_list, '1')
    for city_code in city_code_list:
        #  该活动区县的范围
        dist_list += AdministrativeDivision.sync_distinct('title', {'parent_code': city_code})
    quantity = 0
    member_cid_list = RaceMapping.sync_distinct("member_cid", {'race_cid': race_cid, 'auth_address.city': {'$in': city_name_list}, 'auth_address.province': {'$ne': None},'auth_address.district': {'$in': dist_list}})
    check_point_cid = RaceGameCheckPoint.sync_distinct("cid", {"race_cid": race_cid})
    for i in member_cid_list:
        member = Member.sync_get_by_cid(i)
        if member:
            history = MemberCheckPointHistory.sync_find_one({'check_point_cid': {'$in': check_point_cid}, "member_cid": i})
            if not history:
                quantity += 1
    print(quantity)


def check_data():
    day = (datetime.datetime.now() + datetime.timedelta(days=-18)).replace(hour=0, minute=0, second=0)
    race_mapping_list = RaceMapping.sync_find({"race_cid": "CA755167DEA9AA89650D11C10FAA5413", 'created_dt': {'$lt': day}}).to_list(None)
    print(len(race_mapping_list))

if __name__ == '__main__':
    # check("F742E0C7CA5F7E175844478D74484C29")
    #  六安  CA755167DEA9AA89650D11C10FAA5413
    #   贵州  F742E0C7CA5F7E175844478D74484C29
    #   安徽  3040737C97F7C7669B04BC39A660065D
    check_data()