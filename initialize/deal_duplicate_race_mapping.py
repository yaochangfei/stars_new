# !/usr/bin/python
# -*- coding:utf-8 -*-

from pymongo import UpdateOne

from db.models import RaceMapping, Race
from motorengine.stages import MatchStage, GroupStage, ProjectStage


def change_duplicate_race_mapping(race_cid: str):
    print("race_cid:%s" % race_cid)
    match_stage = MatchStage({'race_cid': race_cid,'record_flag':1})
    project_stage = ProjectStage(**{"race_cid": 1, "member_cid": 1, "race_check_point_cid": 1})
    group_stage = GroupStage({'_id': '$member_cid'}, count={'$sum': 1}, duplicate_list={'$push': '$$ROOT'})
    match_stage_count = MatchStage({'count': {'$gt': 1}})
    project_stage_1 = ProjectStage(**{'duplicate_list': 1})
    duplicate_race_mappings = RaceMapping.sync_aggregate(
        [match_stage, project_stage, group_stage, match_stage_count, project_stage_1]).to_list(None)
    count = 1
    if len(duplicate_race_mappings) > 0:
        for duplicate_race_mapping in duplicate_race_mappings:
            print('第%d个:' % count)
            print(duplicate_race_mapping.duplicate_list)
            duplicate_record_ids = [x._id for x in duplicate_race_mapping.duplicate_list]
            not_need_index = 0  # 确定record_flag为1的元素
            for index, value in enumerate(duplicate_race_mapping.duplicate_list):
                if value.race_check_point_cid:
                    not_need_index = index
            duplicate_record_ids.pop(not_need_index)
            print("record_flag需置为0的记录Id:")
            print(duplicate_record_ids)
            update_requests = []
            for object_id in duplicate_record_ids:
                update_requests.append(UpdateOne({'_id': object_id}, {'$set': {'record_flag': 0}}))
            RaceMapping.sync_update_many(update_requests)
            print("-------END:record_flag已置为0---------------")
            count += 1
    else:
        print("-------未找到member_cid重复的记录-------")
    print("-------结束处理活动-------")

if __name__ == '__main__':
    races = Race.sync_find().to_list(None)
    for race in races:
        print("---------当前处理的活动为：%s------------" % race.title)
        print(race.cid)
        change_duplicate_race_mapping(race.cid)
