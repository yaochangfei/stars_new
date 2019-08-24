#! /usr/bin/python


from datetime import datetime

from db.models import MemberDailyDimensionStatistics, MemberGameHistory, Member, Subject
from motorengine.stages import UnwindStage, ProjectStage, MatchStage, GroupStage, LookupStage
from pymongo import ReadPreference


class MemberDailyDimensionStatisticsTemp(MemberDailyDimensionStatistics):
    """
    临时表
    """

    pass


def do_init(model):
    """

    :return:
    """
    b_dt = datetime.now().replace(month=5, day=18, hour=0, minute=0, second=0)
    e_dt = datetime.now().replace(month=6, day=13, hour=0, minute=0, second=0)

    cursor = MemberGameHistory.sync_aggregate([
        MatchStage({'created_dt': {'$gte': b_dt, '$lte': e_dt}}),
        UnwindStage("result"),
        ProjectStage(**{
            'daily_code': {
                '$dateToString': {'format': '%Y%m%d000000', 'date': '$created_dt'}
            },
            'member_cid': 1,
            'subject_cid': '$result.subject_cid',
            'true_answer': "$result.true_answer",
            'created_dt': 1
        }),
        GroupStage({'daily_code': '$daily_code', 'member_cid': '$member_cid', 'subject_cid': '$subject_cid'},
                   answer_list={'$push': '$true_answer'}, created_dt={'$first': '$created_dt'}),
        LookupStage(Member, '_id.member_cid', 'cid', 'member_list'),
        LookupStage(Subject, '_id.subject_cid', 'cid', 'subject_list'),
        MatchStage({'member_list': {'$ne': []}, 'subject_list': {'$ne': []}}),
        ProjectStage(**{
            'member_cid': '$_id.member_cid',
            'dimension': {"$arrayElemAt": ['$subject_list.dimension_dict', 0]},
            'daily_code': '$_id.daily_code',
            'province_code': {"$arrayElemAt": ['$member_list.province_code', 0]},
            'city_code': {"$arrayElemAt": ['$member_list.city_code', 0]},
            'district_code': {"$arrayElemAt": ['$member_list.district_code', 0]},
            'gender': {"$arrayElemAt": ['$member_list.sex', 0]},
            'age_group': {"$arrayElemAt": ['$member_list.age_group', 0]},
            'education': {"$arrayElemAt": ['$member_list.education', 0]},
            'correct': {
                '$size': {
                    '$filter': {'input': '$answer_list', 'as': 'item',
                                'cond': {'$and': [{'$eq': ['$$item', True]}]}}
                }
            },
            'total': {"$size": "$answer_list"},
            'created_dt': 1
        }),
        GroupStage({'daily_code': '$daily_code', 'member_cid': '$member_cid', 'dimension': '$dimension'},
                   province_code={'$first': "$province_code"}, city_code={'$first': "$city_code"},
                   district_code={'$first': "$district_code"}, gender={'$first': "$gender"},
                   age_group={'$first': "$age_group"}, education={'$first': "$education"},
                   correct={'$sum': "$correct"}, total={'$sum': '$total'})
    ], allowDiskUse=True, read_preference=ReadPreference.PRIMARY)

    index = 0
    while True:
        try:
            data = cursor.next()
            param = {
                'daily_code': data.id.get('daily_code'),
                'member_cid': data.id.get('member_cid'),
                'dimension': data.id.get('dimension'),
                'province_code': data.province_code,
                'city_code': data.city_code,
                'district_code': data.district_code,
                'gender': data.gender,
                'age_group': data.age_group,
                'education': data.education,
                'subject_total_quantity': data.total,
                'subject_correct_quantity': data.correct,
                'created_dt': data.created_dt
            }

            model(**param).sync_save()

            index += 1
            print('has exec', index)
        except StopIteration:
            break
        except AttributeError as e:
            print(e)
            continue

    print('done.')


if __name__ == '__main__':
    do_init(MemberDailyDimensionStatisticsTemp)
