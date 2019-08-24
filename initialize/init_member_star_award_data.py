# !/usr/bin/python

import datetime
import traceback

from pymongo import ReadPreference

from db import TYPE_DAN_GRADE_ONE, DAN_STAR_GRADE_MAPPING, STATUS_RESULT_GAME_PK_WIN, TYPE_DAN_GRADE_ELEVEN, \
    STATUS_USER_ACTIVE, TYPE_STAR_GRADE_FIVE
from db.models import MemberGameHistory, MemberStarsAwardHistory, Member
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage
from motorengine.stages.group_stage import GroupStage


def get_fight_history_models():
    # 获取对战历史
    return MemberGameHistory.sync_find({
        'status': STATUS_RESULT_GAME_PK_WIN,
        'fight_datetime': {'$ne': None}
    }, read_preference=ReadPreference.PRIMARY).sort([('fight_datetime', ASC)]).batch_size(32)


def deal_with_history():
    count = 1
    fight_history_list = get_fight_history_models()
    for index, fight_history in enumerate(fight_history_list):
        if fight_history:
            member = Member.sync_get_by_cid(fight_history.member_cid)
            if member:
                do_calculate_member_stars_award(member, fight_history)
                print(count, member.nick_name, fight_history.fight_datetime)
                count += 1


def do_calculate_member_stars_award(member, fight_history):
    if member and fight_history and be_award(member, fight_history):
        stars_award_history = MemberStarsAwardHistory(
            member_cid=member.cid,
            dan_grade=fight_history.dan_grade,
            quantity=1,
            award_dt=fight_history.fight_datetime)
        stars_award_history.sync_save()


def be_award(member, fight_history):
    if member and fight_history:
        dan_grade = fight_history.dan_grade
        if not dan_grade:
            dan_grade = TYPE_DAN_GRADE_ONE
        need_stars = DAN_STAR_GRADE_MAPPING.get(dan_grade)
        if need_stars:
            awarded_stars = get_awarded_stars(member, fight_history)
            if dan_grade == TYPE_DAN_GRADE_ELEVEN:
                return True
            if awarded_stars < need_stars:
                return True
    return False


def get_awarded_stars(member, fight_history):
    count = 0
    if member and fight_history:
        try:
            award_history_list = MemberStarsAwardHistory.sync_aggregate([
                MatchStage({
                    'member_cid': member.cid,
                    'award_dt': {'$lte': fight_history.fight_datetime},
                    'dan_grade': fight_history.dan_grade
                }),
                GroupStage('member_cid', count={'$sum': '$quantity'})
            ]).to_list(1)
            if award_history_list:
                print('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa')
                award_history = award_history_list[0]
                if award_history:
                    count = award_history.count
        except Exception:
            print(traceback.format_exc())
    return count


def init_member_star():
    members = Member.sync_find({'status': STATUS_USER_ACTIVE}).batch_size(32)
    for index, member in enumerate(members):
        print(index+1, member.nick_name)
        quantity = 0
        if member.star_grade is None or member.star_grade == 0:
            if member.dan_grade:
                quantity = get_need_star(member.dan_grade)
        else:
            quantity = get_need_star(member.dan_grade) + member.star_grade

        stars_award_history = MemberStarsAwardHistory(
            member_cid=member.cid,
            dan_grade=member.dan_grade if member.dan_grade else 1,
            quantity=quantity,
            award_dt=datetime.datetime(2018, 10, 15, 0, 0, 0, 0))
        stars_award_history.sync_save()


def get_need_star(dan_grade):
    if not dan_grade:
        dan_grade = 1
    star_count = 0
    for i in range(1, dan_grade):
        star_count += DAN_STAR_GRADE_MAPPING.get(i)
    return star_count


if __name__ == '__main__':
    init_member_star()
