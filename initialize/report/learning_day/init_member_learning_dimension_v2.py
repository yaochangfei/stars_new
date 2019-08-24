#! /usr/bin/python


import time

from db.models import MemberGameHistory, MemberLearningDayDimensionStatistics, Subject, Member
from motorengine.stages import ProjectStage, GroupStage, UnwindStage, LookupStage
from pymongo import ReadPreference


class MemberLearningDayDimensionStatisticsTemp(MemberLearningDayDimensionStatistics):
    pass


def do_stat(model):
    stage_list = [
        UnwindStage('result'),
        ProjectStage(**{
            'daily_code': {
                '$dateToString': {'format': '%Y%m%d', 'date': '$created_dt'}
            },
            'member_cid': '$member_cid',
            'subject_cid': '$result.subject_cid',
            'true_answer': '$result.true_answer'
        }),
        LookupStage(Subject, 'subject_cid', 'cid', 'subject_list'),
        ProjectStage(**{
            'daily_code': 1,
            'member_cid': 1,
            'true_answer': 1,
            'dimension': {'$arrayElemAt': ['$subject_list.dimension_dict', 0]}
        }),
        GroupStage({'daily_code': '$daily_code', 'member_cid': '$member_cid', 'dimension': '$dimension'},
                   answer_list={'$push': '$true_answer'}),
        ProjectStage(**{
            'daily_code': '$_id.daily_code',
            'member_cid': '$_id.member_cid',
            'dimension': '$_id.dimension',
            'correct': {
                '$size': {
                    '$filter': {'input': '$answer_list', 'as': 'item', 'cond': {'$and': [{'$eq': ['$$item', True]}]}}
                }
            },
            'total': {
                "$size": "$answer_list"
            }
        }),
        GroupStage({'member_cid': '$member_cid', 'dimension': '$dimension'},
                   daily_list={'$push': '$daily_code'}, correct_list={'$push': '$correct'},
                   total_list={'$push': '$total'}),
    ]

    cursor = MemberGameHistory.sync_aggregate(stage_list, allowDiskUse=True, read_preference=ReadPreference.PRIMARY)

    t1 = time.time()
    index = 0
    insert_list = []
    while True:
        try:
            data = cursor.next()

            member = Member.sync_get_by_cid(data.id.get('member_cid'))
            if not member:
                continue

            dimension = data.id.get('dimension')
            if not dimension:
                continue

            for i, day in enumerate(data.daily_list):
                param = {
                    'learning_code': get_learning_code(day, data.daily_list),
                    'member_cid': member.cid,
                    'dimension': dimension,
                    'province_code': member.province_code,
                    'city_code': member.city_code,
                    'district_code': member.district_code,
                    'gender': member.sex,
                    'age_group': member.age_group,
                    'education': member.education,
                    'subject_total_quantity': data.total_list[i],
                    'subject_correct_quantity': data.correct_list[i]
                }
                insert_list.append(model(**param))

        except StopIteration:
            break

        if len(insert_list) > 5000:
            model.sync_insert_many(insert_list)
            insert_list = []

        index += 1
        print('has exec', index)

    t2 = time.time()
    print('cost:', t2 - t1)
    model.sync_insert_many(insert_list)
    t3 = time.time()
    print('insert', t3 - t2)


def get_learning_code(daily_code, daily_list):
    """
    获取学习日编号
    :param daily_code:
    :param daily_list:
    :return:
    """
    count = 0
    for day in daily_list:
        if day <= daily_code:
            count += 1

    return count


if __name__ == '__main__':
    do_stat(MemberLearningDayDimensionStatisticsTemp)
