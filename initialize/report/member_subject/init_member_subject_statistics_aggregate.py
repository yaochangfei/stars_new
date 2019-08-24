#! /usr/bin/python


import traceback
from datetime import datetime

from pymongo import ReadPreference
from db.models import MemberGameHistory, Member, MemberSubjectStatistics, Subject
from motorengine import ASC
from motorengine.stages import MatchStage, UnwindStage, ProjectStage, GroupStage, LookupStage, SortStage, SkipStage, \
    LimitStage, CountStage


class MemberSubjectStatisticsTemp(MemberSubjectStatistics):
    pass


def do_init_member_stat(pre_match: dict = {}, skip_num=0, limit_num=0, just_return_count=False):
    """

    :param pre_match:
    :param skip_num:
    :param limit_num:
    :param just_return_count:
    :return:
    """
    if not isinstance(just_return_count, bool):
        raise Exception('check params(just_return_count)')

    stage_list = []
    if pre_match:
        stage_list.append(MatchStage(pre_match))

    stage_list.extend([
        UnwindStage("result"),
        LookupStage(Member, 'member_cid', 'cid', 'member_list'),
        MatchStage({'member_list': {'$ne': list()}}),
        ProjectStage(**{
            'subject_cid': '$result.subject_cid',
            'province_code': {'$arrayElemAt': ['$member_list.province_code', 0]},
            'city_code': {'$arrayElemAt': ['$member_list.city_code', 0]},
            'district_code': {'$arrayElemAt': ['$member_list.district_code', 0]},
            'sex': {'$arrayElemAt': ['$member_list.sex', 0]},
            'age_group': {'$arrayElemAt': ['$member_list.age_group', 0]},
            'category': {'$arrayElemAt': ['$member_list.category', 0]},
            'education': {'$arrayElemAt': ['$member_list.education', 0]},
            'true_answer': {'$cond': {'if': {'$eq': ['$result.true_answer', True]}, 'then': True, 'else': False}},
            'created_dt': '$created_dt'
        }),
        GroupStage({
            'subject_cid': '$subject_cid',
            'province_code': '$province_code',
            'city_code': '$city_code',
            'district_code': '$district_code',
            'sex': '$sex',
            'age_group': '$age_group',
            'category': '$category',
            'education': '$education',
        }, answers_list={'$push': '$true_answer'}, created_dt={'$first': '$created_dt'}),
    ])

    if just_return_count:
        stage_list.append(CountStage())
        data = MemberGameHistory.sync_aggregate(stage_list, read_preference=ReadPreference.PRIMARY,
                                                allowDiskUse=True).to_list(1)
        return data[0].count

    stage_list.append(SortStage([('created_dt', ASC)]))
    if skip_num:
        stage_list.append(SkipStage(skip_num))
    if limit_num:
        stage_list.append(LimitStage(limit_num))

    cursor = MemberGameHistory.sync_aggregate(stage_list, read_preference=ReadPreference.PRIMARY,
                                              allowDiskUse=True).batch_size(256)

    index = 0
    _subject_map = {}
    while True:
        try:
            data = cursor.next()

            subject_cid = data.id.get('subject_cid')
            subject = _subject_map.get(subject_cid)
            if not subject:
                subject = Subject.sync_get_by_cid(subject_cid)
                _subject_map[subject_cid] = subject

            write_member_subject_stat(data, subject)

            index += 1
            print('has exec %s' % index)
        except StopIteration:
            break
        except Exception:
            print(traceback.format_exc())
            continue


def write_member_subject_stat(data, subject):
    """

    :param data:
    :param subject:
    :return:
    """
    if not subject:
        print('there is no subject.')
        return

    mds = MemberSubjectStatisticsTemp(province_code=data.id.get('province_code'),
                                      city_code=data.id.get('city_code'),
                                      district_code=data.id.get('district_code'), gender=data.id.get('sex'),
                                      age_group=data.id.get('age_group'),
                                      education=data.id.get('education'), category=data.id.get('category'),
                                      subject_cid=subject.cid,
                                      dimension=subject.dimension_dict)

    mds.total = len(data.answers_list)
    mds.correct = data.answers_list.count(True)
    mds.created_dt = data.created_dt
    mds.updated_dt = data.created_dt
    mds.sync_save()


if __name__ == '__main__':
    import sys

    skip_num = int(sys.argv[1])
    limit_num = int(sys.argv[2])
    do_init_member_stat({}, skip_num=skip_num, limit_num=limit_num)
