#! /usr/bin/python


import getopt
import sys
from datetime import datetime
from db.models import MemberDailyStatistics, MemberGameHistory, Member, Subject
from motorengine import ASC
from motorengine.stages import ProjectStage, GroupStage, LookupStage, SortStage, MatchStage, SkipStage, LimitStage
from collections import Counter
from pymongo import ReadPreference


class MemberDailyStatisticsTemp(MemberDailyStatistics):
    """
    临时表
    """
    pass


def get_dimension_detail(result_list: list):
    """

    :param result_list:
    :return:
    """

    dimension_detail = {}
    for result in result_list:
        for answer in result:
            subject = Subject.sync_get_by_cid(answer.get('subject_cid'))
            for fst_dimen, sec_dimen in subject.dimension_dict.items():
                if fst_dimen not in dimension_detail:
                    dimension_detail[fst_dimen] = {'total': 0, 'correct': 0}
                if sec_dimen not in dimension_detail[fst_dimen]:
                    dimension_detail[fst_dimen][sec_dimen] = {'total': 0, 'correct': 0}

                dimension_detail[fst_dimen]['total'] += 1
                dimension_detail[fst_dimen][sec_dimen]['total'] += 1
                if answer.get('true_answer'):
                    dimension_detail[fst_dimen]['correct'] += 1
                    dimension_detail[fst_dimen][sec_dimen]['correct'] += 1

    return dimension_detail


def do_init(model, skip_num, limit_num):
    """

    :param model:
    :param skip_num:
    :param limit_num:
    :return:
    """
    stage_list = [
        MatchStage({'created_dt': {"$gte": datetime.now().replace(day=14, hour=18, minute=15, second=00),
                                   "$lte": datetime.now().replace(day=17, hour=9, minute=22, second=00)}}),
        ProjectStage(**{
            'daily_code': {"$dateToString": {'format': '%Y%m%d000000', 'date': "$created_dt"}},
            'member_cid': 1,
            'correct': {
                '$size': {
                    '$filter': {'input': '$result.true_answer', 'as': 'item',
                                'cond': {'$and': [{'$eq': ['$$item', True]}]}}
                }
            },
            'total': {'$size': '$result'},
            'result': 1,
            'created_dt': 1
        }),
        GroupStage({'daily_code': '$daily_code', 'member_cid': '$member_cid'},
                   correct_list={'$push': "$correct"}, result_list={"$push": "$result"},
                   created_dt={'$first': "$created_dt"},
                   correct={'$sum': '$correct'}, total={'$sum': '$total'}, learn_times={'$sum': 1}),
        LookupStage(Member, '_id.member_cid', 'cid', 'member_list'),
        MatchStage({'member_list': {'$ne': []}}),
        ProjectStage(**{
            'daily_code': "$_id.daily_code",
            'member_cid': '$_id.member_cid',
            'correct': '$correct',
            'total': "$total",
            'correct_list': "$correct_list",
            'learn_times': '$learn_times',
            'province_code': {"$arrayElemAt": ['$member_list.province_code', 0]},
            'city_code': {"$arrayElemAt": ['$member_list.city_code', 0]},
            'district_code': {"$arrayElemAt": ['$member_list.district_code', 0]},
            'gender': {"$arrayElemAt": ['$member_list.sex', 0]},
            'age_group': {"$arrayElemAt": ['$member_list.age_group', 0]},
            'education': {"$arrayElemAt": ['$member_list.education', 0]},
            'result_list': 1,
            'created_dt': 1
        }),
        SortStage([('daily_code', ASC), ('member_cid', ASC)]),
    ]

    if skip_num:
        stage_list.append(SkipStage(skip_num))
    if limit_num:
        stage_list.append(LimitStage(limit_num))

    cursor = MemberGameHistory.sync_aggregate(stage_list, allowDiskUse=True, read_preference=ReadPreference.PRIMARY)

    index = 0
    while True:
        try:
            index += 1
            print('has exec %s.' % index)
            data = cursor.next()

            param = {
                'daily_code': data.daily_code,
                'member_cid': data.member_cid,
                'province_code': data.province_code,
                'city_code': data.city_code,
                'district_code': data.district_code,
                'gender': data.gender,
                'age_group': data.age_group,
                'education': data.education,
                'learn_times': data.learn_times,
                'subject_total_quantity': data.total,
                'subject_correct_quantity': data.correct,
                'quantity_detail': dict(Counter(map(lambda x: str(x), data.correct_list))),
                'dimension_detail': get_dimension_detail(data.result_list),
                'created_dt': data.created_dt,
                'updated_dt': data.created_dt
            }

            model(**param).sync_save()
        except StopIteration:
            break
        except AttributeError as e:
            print(e)
            continue


def usage():
    print('usage: python [option] ... [arg] ...\n'
          '\n'
          '-h --help \n'
          '-s --skip : skip num \n'
          'sl --limit: limit num \n')


if __name__ == '__main__':
    skip = limit = 0
    opts, args = getopt.gnu_getopt(sys.argv[1:], 'hs:l:', ['skip=', 'limit=', 'help'])
    for op, value in opts:
        if op == "-s" or op == '--skip':
            skip = value
        elif op == "-l" or op == '--limit':
            limit = value
        elif op == "-h" or op == '--help':
            usage()
            exit(1)

    do_init(MemberDailyStatisticsTemp, int(skip), int(limit))
