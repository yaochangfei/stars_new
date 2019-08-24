# !/usr/bin/python

import datetime
import hashlib
import json
import math
import random
import time

import aiohttp
from bson import ObjectId
from caches.redis_utils import RedisCache
from commons.division_utils import get_matched_division_2_dict
from db import SEX_LIST, TYPE_AGE_GROUP_LIST, TYPE_EDUCATION_LIST, TYPE_AGE_GROUP_NONE, TYPE_AGE_GROUP_YOUNG, \
    TYPE_AGE_GROUP_MIDDLE, TYPE_AGE_GROUP_OLD, TYPE_EDUCATION_NONE, TYPE_EDUCATION_JUNIOR, TYPE_EDUCATION_SENIOR, \
    TYPE_EDUCATION_COLLEGE, TYPE_EDUCATION_BACHELOR, TYPE_EDUCATION_MASTER, SEX_NONE, SEX_MALE, SEX_FEMALE, \
    MAX_RESPOND_SECONDS, KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT, STATUS_SUBJECT_DIMENSION_ACTIVE, \
    STATUS_GAME_DAN_GRADE_ACTIVE, SOURCE_MEMBER_DIAMOND_LIST, \
    SOURCE_MEMBER_DIAMOND_DICT, SOURCE_MEMBER_DIAMOND_FIRST_PK, STATUS_RESULT_GAME_PK_WIN, \
    SOURCE_MEMBER_DIAMOND_FIRST_WIN, SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES, \
    SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND, TYPE_DAN_GRADE_ONE, \
    TYPE_STAR_GRADE_ONE, DAN_STAR_GRADE_MAPPING, STATUS_RESULT_GAME_PK_GIVE_UP, \
    STATUS_WRONG_SUBJECT_INACTIVE, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, \
    STATUS_RESULT_GAME_PK_TIE_BREAK, SOURCE_MEMBER_DIAMOND_PK_VICTORY, STATUS_RESULT_GAME_PK_FAILED, \
    TYPE_DAN_GRADE_ELEVEN, STATUS_ACTIVE, TYPE_MSG_LOTTERY, TYPE_MSG_DRAW, CATEGORY_NOTICE_AWARD, STATUS_NOTICE_READ
from db.model_utils import set_cached_subject_accuracy, get_cached_subject_accuracy, update_diamond_reward
from db.models import SubjectBanks, Subject, FightRobotAnalysisReference, Member, UploadFiles, SubjectDimension, \
    GameDanGrade, MemberGameHistory, SubjectOption, GameDiamondReward, MemberDiamondDetail, MemberStarsAwardHistory, \
    MemberWrongSubject, GameDiamondConsume, Race, RaceGameCheckPoint, RedPacketRule, MemberNotice, RedPacketBox, \
    RedPacketItemSetting
from enums import KEY_PREFIX_SUBJECT_BANKS_COUNT, KEY_PREFIX_DAN_GRADE_LIST, KEY_CACHE_LOTTERY_TABLE
from motorengine import FacadeO, ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, LimitStage
from motorengine.stages.group_stage import GroupStage
from motorengine.stages.project_stage import ProjectStage
from settings import SERVER_HOST, SERVER_PROTOCOL, STATIC_URL_PREFIX, REDPACKET_PLATFORM_PROJECT_ID, \
    REDPACKET_PLATFORM_SECRECT_KEY
from tasks.instances.task_accurate_statistics import start_accurate_statistics
from tasks.instances.task_report_dashboard_statistics import start_dashboard_report_statistics
from tasks.instances.task_robot_analysis_reference import task_robot_analysis_reference_statistics
from pymongo import ReadPreference

DEFAULT_WORDS = 64
# 最长时间系数
MIN_SECONDS_FACTOR = 0.1
MAX_SECONDS_FACTOR = 0.7
# 阅读速度
READING_SPEED = {
    TYPE_AGE_GROUP_NONE: 12,
    TYPE_AGE_GROUP_YOUNG: 14,
    TYPE_AGE_GROUP_MIDDLE: 16,
    TYPE_AGE_GROUP_OLD: 10,
}

# 正确率系数
EDUCATION_ACCURACY_FACTOR = {
    TYPE_EDUCATION_NONE: 0.60,
    TYPE_EDUCATION_JUNIOR: 0.40,
    TYPE_EDUCATION_SENIOR: 0.60,
    TYPE_EDUCATION_COLLEGE: 0.70,
    TYPE_EDUCATION_BACHELOR: 0.75,
    TYPE_EDUCATION_MASTER: 0.80
}

# 性别正确率
GENDER_ACCURACY_FACTOR = {
    SEX_NONE: 1,
    SEX_MALE: 1.05,
    SEX_FEMALE: 0.95
}


async def do_get_suite_subject_list(rule_cid: str, member: Member = None):
    """
    获取套题
    :param rule_cid:
    :param member:
    :return:
    """
    try:
        subject_list = await do_get_suite_subject_and_set_robot_info(rule_cid, member)
        if not subject_list:
            raise AttributeError('No subject returned.')
    except AttributeError:
        subject_list = await do_get_suite_subject_and_set_robot_info(rule_cid, member)
    return subject_list


async def do_get_suite_subject_and_set_robot_info(rule_cid: str, member: Member = None):
    """
    填充套题机器人信息
    :param rule_cid:
    :param member:
    :return:
    """
    if rule_cid:
        subject_list = await do_query_fight_subjects_by_rule_cid(rule_cid)
        if subject_list:
            subject_cid_list = [subject.cid for subject in subject_list]
            if subject_cid_list:
                kwargs = {}
                if member:
                    if member.sex is not None:
                        kwargs['gender'] = member.sex
                    if member.age_group is not None:
                        kwargs['age_group'] = member.age_group
                    if member.education is not None:
                        kwargs['education'] = member.education
                stat_data: dict = await do_get_subject_analysis_stat_data(subject_cid_list, **kwargs)
                for subject in subject_list:
                    do_set_subject_robot_info(subject, stat_data, member)
                return subject_list
    return []


def do_set_subject_robot_info(subject: FacadeO, stat_data: dict = None, member: Member = None):
    """
    填充题目机器人信息
    :param subject:
    :param stat_data:
    :param member:
    :return:
    """
    if subject is not None:
        if not stat_data:
            stat_data = {}

        robot_data: dict = stat_data.get(subject.cid, {})
        words = robot_data.get('words', DEFAULT_WORDS)
        accuracy = do_get_subject_final_accuracy(robot_data.get('accuracy'), member)

        is_correct = do_judge_subject_correctness(accuracy)
        if is_correct:
            stat_seconds = robot_data.get('correct_seconds')
        else:
            stat_seconds = robot_data.get('incorrect_seconds')

        seconds = do_get_subject_final_seconds(stat_seconds, words, member)

        # 设置属性
        setattr(subject, 'is_correct', is_correct)
        setattr(subject, 'answer_seconds', seconds)

        correct_option_cid = None
        incorrect_option_cid_list = []

        option_list = subject.option_list
        for index, option in enumerate(option_list):
            fo = FacadeO(option)
            subject.option_list[index] = fo
            if fo:
                if fo.correct:
                    correct_option_cid = fo.cid
                else:
                    incorrect_option_cid_list.append(fo.cid)
        if is_correct:
            setattr(subject, 'choice_option_cid', correct_option_cid)
        else:
            setattr(subject, 'choice_option_cid', random.choice(incorrect_option_cid_list))


def do_judge_subject_correctness(accuracy):
    """
    判断是否给出正确答案
    :param accuracy:
    :return:
    """
    if accuracy:
        if random.random() <= accuracy:
            return True
        else:
            return False
    return False


def do_get_subject_final_accuracy(stat_accuracy, member: Member = None):
    """
    获取题目最终正确率
    :param stat_accuracy:
    :param member:
    :return:
    """
    edu_factor = EDUCATION_ACCURACY_FACTOR[TYPE_EDUCATION_NONE]
    if member and member.education is not None:
        edu_factor = EDUCATION_ACCURACY_FACTOR.get(member.education, edu_factor)
    sex_factor = GENDER_ACCURACY_FACTOR[SEX_NONE]
    if member and member.sex is not None:
        sex_factor = GENDER_ACCURACY_FACTOR.get(member.sex, sex_factor)

    final_accuracy = edu_factor * sex_factor
    if stat_accuracy:
        final_accuracy = stat_accuracy * edu_factor * sex_factor
    return final_accuracy if final_accuracy <= 1 else 1.0


def do_get_subject_final_seconds(stat_seconds=None, words=DEFAULT_WORDS, member: Member = None):
    """
    计算题目给出答案时间
    :param stat_seconds:
    :param words:
    :param member:
    :return:
    """
    seconds = stat_seconds
    if stat_seconds is None or stat_seconds < MAX_RESPOND_SECONDS * MIN_SECONDS_FACTOR or \
            stat_seconds > MAX_RESPOND_SECONDS * MAX_SECONDS_FACTOR:
        reading_speed = READING_SPEED[TYPE_AGE_GROUP_NONE]
        if member and member.age_group:
            reading_speed = READING_SPEED.get(member.age_group, reading_speed)
        seconds = words / reading_speed if words else DEFAULT_WORDS / reading_speed
        if seconds < MAX_RESPOND_SECONDS * MIN_SECONDS_FACTOR:
            seconds = MAX_RESPOND_SECONDS * MIN_SECONDS_FACTOR
        elif seconds > MAX_RESPOND_SECONDS * MAX_SECONDS_FACTOR:
            seconds = MAX_RESPOND_SECONDS * MAX_SECONDS_FACTOR
        seconds = int(round(seconds, 0))
    return seconds


async def do_get_subject_analysis_stat_data(subject_cid_list, gender=None, age_group=None, education=None):
    """
    获取机器题目分析统计数据
    :param subject_cid_list:
    :param gender:
    :param age_group:
    :param education:
    :return:
    """
    if subject_cid_list:
        data = {}
        match_dict = {'subject_cid': {'$in': subject_cid_list}}
        if gender and gender in SEX_LIST:
            match_dict['gender'] = gender
        if age_group and age_group in TYPE_AGE_GROUP_LIST:
            match_dict['age_group'] = age_group
        if education and education in TYPE_EDUCATION_LIST:
            match_dict['education'] = education

        robot_analysis_cursor = FightRobotAnalysisReference.aggregate([
            MatchStage(match_dict),
            GroupStage(
                group_field='subject_cid',
                accuracy={'$avg': '$accuracy'},
                avg_correct_seconds={'$avg': '$avg_correct_seconds'},
                avg_incorrect_seconds={'$avg': '$avg_incorrect_seconds'},
                words={'$avg': '$words'}),
        ])
        while await robot_analysis_cursor.fetch_next:
            robot_analysis = robot_analysis_cursor.next_object()
            data[robot_analysis.oid] = {
                'accuracy': robot_analysis.accuracy,
                'correct_seconds': math.ceil(robot_analysis.avg_correct_seconds),
                'incorrect_seconds': math.ceil(robot_analysis.avg_incorrect_seconds),
                'words': int(robot_analysis.words)
            }
        return data
    return None


async def do_query_fight_subjects_by_rule_cid(rule_cid: str):
    """
    依据抽题规则CID查询题目
    :param rule_cid:
    :return:
    """
    if rule_cid:
        count = await get_subject_bank_quantity(rule_cid)
        if count > 0:
            # 获取题目
            subject_bank_list = await SubjectBanks.find(dict(rule_cid=rule_cid)).skip(
                random.randint(1, count - 1)).limit(1).to_list(1)
            if subject_bank_list:
                subject_bank_list = await SubjectBanks.aggregate([
                    MatchStage({'_id': ObjectId(subject_bank_list[0].oid)}),
                    LookupStage(
                        foreign=Subject,
                        let=dict(subject_cid_list='$subject_cid_list'),
                        as_list_name='subject_list',
                        pipeline=[{
                            '$match': {
                                '$expr': {
                                    '$and': [
                                        {'$in': ['$cid', '$$subject_cid_list']},
                                        {'$eq': ['$status', 1]},
                                    ]
                                }
                            }
                        }, {
                            '$lookup': {
                                'from': 'TBL_SUBJECT_OPTION',
                                'let': {'subject_cid': '$cid'},
                                'pipeline': [{
                                    '$match': {
                                        '$expr': {
                                            '$and': [
                                                {'$eq': ['$subject_cid', '$$subject_cid']}
                                            ]
                                        }
                                    }
                                }, {
                                    '$sort': {
                                        'code': 1
                                    }
                                }],
                                'as': 'option_list'
                            }
                        }]
                    ),
                    ProjectStage(subject_list='$subject_list')
                ]).to_list(1)

                if subject_bank_list:
                    return subject_bank_list[0].subject_list
    return None


async def parse_wechat_info(wechat_info) -> dict:
    """
    解析用户信息
    :param wechat_info:
    :return:
    """
    result = {}
    if wechat_info:
        division_dict = {}
        try:
            province_name = None
            city_name = None
            district_name = None
            if wechat_info.get('address'):
                if len(wechat_info.get('address')) > 0:
                    province_name = wechat_info.get('address')[0]
                if len(wechat_info.get('address')) > 1:
                    city_name = wechat_info.get('address')[1]
                    city_name = city_name.replace('市', '')
                if len(wechat_info.get('address')) > 2:
                    district_name = wechat_info.get('address')[2]
                    district_name = district_name.replace('区', '').replace('县', '')
                division_dict = await get_matched_division_2_dict(province_name=province_name,
                                                                  city_name=city_name,
                                                                  district_name=district_name
                                                                  )
            else:
                division_dict = await get_matched_division_2_dict(province_name=wechat_info.get('province'),
                                                                  city_name=wechat_info.get('city'),
                                                                  district_name=wechat_info.get('district', None)
                                                                  )
        except ValueError:
            pass
        result['province_code'] = division_dict.get('P').get('code') if division_dict.get('P') else None
        result['province_name'] = division_dict.get('P').get('title') if division_dict.get('P') else None
        result['city_code'] = division_dict.get('C').get('code') if division_dict.get('C') else None
        result['city_name'] = division_dict.get('C').get('title') if division_dict.get('C') else None
        result['district_code'] = division_dict.get('D').get('code') if division_dict.get('D') else None
        result['district_name'] = division_dict.get('D').get('title') if division_dict.get('D') else None
        result['avatar'] = wechat_info.get('avatar_url')
        result['nick_name'] = wechat_info.get('nick_name')
    return result


async def get_subject_bank_quantity(rule_cid: str):
    """
    获取题库套数
    :param rule_cid: 抽题规则CID
    :return:
    """
    # 获取题目数量
    cache_key = '%s_%s' % (KEY_PREFIX_SUBJECT_BANKS_COUNT, rule_cid)
    count = RedisCache.get(cache_key)
    if count is None:
        count = await SubjectBanks.count(dict(rule_cid=rule_cid))
        RedisCache.set(cache_key, count)
    return int(count)


async def deal_subject_list(subject_list: list):
    """
    处理获取到的排位赛题目
    :param subject_list:
    :return:
    """
    question_list = []
    answer_list = []
    if subject_list:
        sub_category_subject_dimension_dict, difficulty_subject_dimension_list = await get_dimension_info()
        difficulty_count = len(difficulty_subject_dimension_list)
        difficulty_subject_dimension_cid_list = [difficulty_subject_dimension.cid for difficulty_subject_dimension
                                                 in difficulty_subject_dimension_list]
        upload_file_dict = {}
        file_cid_list = [subject.image_cid for subject in subject_list]
        if file_cid_list:
            upload_file_list = await UploadFiles.find(dict(cid={'$in': file_cid_list})).to_list(None)
            for upload_file in upload_file_list:
                upload_file_dict[upload_file.cid] = upload_file.title
        for subject in subject_list:
            # 题目数据
            dimension_dict = subject.dimension_dict
            # 学科部类 CSK001
            category_subject_dimension = sub_category_subject_dimension_dict.get(
                dimension_dict.get(CATEGORY_SUBJECT_DIMENSION_ID))
            # 题目难度 CSD001

            difficult_dimension_cid = dimension_dict.get(DIFFICULTY_SUBJECT_DIMENSION_ID)
            difficulty_subject_dimension_index = difficulty_subject_dimension_cid_list.index(
                difficult_dimension_cid) + 1
            difficulty_list = []
            for i in range(1, 6):
                if difficulty_subject_dimension_index >= i:
                    temp_difficulty = {
                        'show': 'star_degree'
                    }
                else:
                    temp_difficulty = {
                        'show': ''
                    }
                difficulty_list.append(temp_difficulty)
            title_picture = upload_file_dict.get(subject.image_cid, '')
            title_picture_url = ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            question_dict = {
                'id': subject.cid,
                'title': subject.title,
                'picture_url': title_picture_url,
                'category_name': category_subject_dimension.title if category_subject_dimension else '',
                'timeout': 20,
                'difficulty_degree': '%s/%s' % (difficulty_subject_dimension_index, difficulty_count),
                # 'difficulty_list': difficulty_list,
                'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
                'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
                'resolving': subject.resolving,
            }
            option_list = []
            for option in subject.option_list:
                option_dict = {
                    'title': option.title,
                    'id': option.cid,
                    'true_answer': option.correct,
                }
                option_list.append(option_dict)
            question_dict['option_list'] = option_list
            question_list.append(question_dict)
            # 答案数据
            answer_dict = {
                'remain_time': 20 - subject.answer_seconds,
                'question_id': subject.cid,
                'option_id': subject.choice_option_cid,
                'true_answer': subject.is_correct
            }
            answer_list.append(answer_dict)
    return question_list, answer_list


# 学科部类 CSK001
CATEGORY_SUBJECT_DIMENSION_ID = '18114DC7C31B17AE35841CAE833161A2'
# 题目难度 CSD001
DIFFICULTY_SUBJECT_DIMENSION_ID = '8187881ABEAD2CF4A4F24C0AA02B2C2D'
# 知识维度 CDS001
KNOWLEDGE_SUBJECT_DIMENSION_ID = '5D17BEF2B0398FC461DC076E881978C1'


# async def get_dimension_info():
#     subject_dimension_list = await SubjectDimension.aggregate([
#         MatchStage(dict(cid={'$in': dimension_cid_list})),
#         LookupStage(SubjectDimension, 'cid', 'parent_cid', 'sub_subject_dimension_list')
#         ]
#     )
#
#     subject_dimension_list = await SubjectDimension.find(
#         dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).to_list(None)
#     subject_dimension_dict = {}
#     subject_dimension_id_list = []
#     for subject_dimension in subject_dimension_list:
#         subject_dimension_id_list.append(subject_dimension.cid)
#         subject_dimension_dict[subject_dimension.code] = subject_dimension.cid
#     sub_subject_dimension_list = await SubjectDimension.find(
#         dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid={'$in': subject_dimension_id_list}))
#     sub_subject_dimension_dict = {}
#     for sub_subject_dimension in sub_subject_dimension_list:
#         sub_subject_dimension_dict[sub_subject_dimension.cid] = sub_subject_dimension
#
#     return subject_dimension_dict, sub_subject_dimension_dict

async def get_dimension_info():
    """
    获取维度信息
    :return:
    """
    sub_category_subject_dimension_list = await SubjectDimension.find(
        dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=CATEGORY_SUBJECT_DIMENSION_ID)).to_list(None)
    difficulty_subject_dimension_list = await SubjectDimension.find(
        dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=DIFFICULTY_SUBJECT_DIMENSION_ID)).sort(
        [('ordered', ASC)]).to_list(None)
    sub_category_subject_dimension_dict = {}
    for sub_category_subject_dimension in sub_category_subject_dimension_list:
        sub_category_subject_dimension_dict[sub_category_subject_dimension.cid] = sub_category_subject_dimension

    return sub_category_subject_dimension_dict, difficulty_subject_dimension_list


async def get_dan_grade_by_index(index: int = None, update=False):
    """

    :param index: 索引
    :param update: 是否需要更新
    :return:
    """
    if not index:
        index = 0
    if update:
        RedisCache.delete(KEY_PREFIX_DAN_GRADE_LIST)
    if not RedisCache.get(KEY_PREFIX_DAN_GRADE_LIST):
        dan_grades = await GameDanGrade.aggregate(stage_list=[MatchStage({'status': STATUS_GAME_DAN_GRADE_ACTIVE}),
                                                              SortStage([('index', ASC)])]).to_list(None)
        RedisCache.set(KEY_PREFIX_DAN_GRADE_LIST, ','.join([dan.title for dan in dan_grades]))

    dan_list = RedisCache.get(KEY_PREFIX_DAN_GRADE_LIST).split(',')
    return dan_list[index - 1]


async def generate_opponent_answers(opponent):
    """
    根据用户，段位和问题编号生成镜像答题
    并返回小程序格式的数据
    :param opponent:
    :return:
    """
    opponent_result = {}
    question_list = []
    opponent_answer_list = []
    fight_result_dict = {}
    init_own_answer_list = []
    fight_subject_cid_list = []
    game_history_list = await MemberGameHistory.aggregate([
        MatchStage({'member_cid': opponent.cid, 'runaway_index': None}),
        SortStage([('dan_grade', DESC), ('created_dt', DESC)]),
        LimitStage(1)
    ]).to_list(1)

    if game_history_list:
        game_history = game_history_list[0]
        if game_history:
            fight_result_list = game_history.result
            if fight_result_list:
                for fight_result in fight_result_list:
                    fight_result_dict[fight_result.get('subject_cid')] = fight_result
                    fight_subject_cid_list.append(fight_result.get('subject_cid'))
    if fight_result_dict:
        subject_dict = {}
        subject_list = await Subject.aggregate([
            MatchStage({'cid': {'$in': fight_subject_cid_list}}),
            LookupStage(SubjectOption, let={'cid': '$cid'},
                        pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                  SortStage([('code', ASC)])], as_list_name='option_list'),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')
        ]).to_list(None)
        for temp in subject_list:
            subject_dict[temp.cid] = temp
        if fight_subject_cid_list:
            sub_category_subject_dimension_dict, difficulty_subject_dimension_list = await get_dimension_info()
            difficulty_count = len(difficulty_subject_dimension_list)
            difficulty_subject_dimension_cid_list = [difficulty_subject_dimension.cid for difficulty_subject_dimension
                                                     in difficulty_subject_dimension_list]
            for index, subject_cid in enumerate(fight_subject_cid_list):
                subject = subject_dict.get(subject_cid)
                if subject:
                    init_own_answer_list.append({'questionid': subject.cid})
                    question = deal_subject(subject, index == 0)
                    if question:
                        result = fight_result_dict.get(subject.cid)
                        if result:
                            o_answer = {
                                'remain_time': 20 - result.get('consume_time', 0),
                                'question_id': subject.cid,
                                'option_id': result.get('selected_option_cid'),
                                'true_answer': result.get('true_answer'),
                                'score': result.get('score', 0)
                            }
                            opponent_answer_list.append(o_answer)
                            question_list.append(question)

    opponent_result['score'] = 0  # 默认是0
    opponent_result['runaway_index'] = ''
    opponent_result['answers'] = opponent_answer_list

    return opponent_result, question_list, init_own_answer_list


def deal_subject(subject, sub_category_subject_dimension_dict, difficulty_subject_dimension_cid_list, difficulty_count,
                 is_current=False):
    if subject:
        title_picture = subject.file_list[0].title if subject.file_list else ''
        if title_picture:
            title_picture_url = f'{SERVER_PROTOCOL}://{SERVER_HOST}{STATIC_URL_PREFIX}files/{title_picture}'
        else:
            title_picture_url = ''
        dimension_dict = subject.dimension_dict
        # 学科部类 CSK001
        category_subject_dimension = sub_category_subject_dimension_dict.get(
            dimension_dict.get(CATEGORY_SUBJECT_DIMENSION_ID))
        # 题目难度 CSD001
        difficult_dimension_cid = dimension_dict.get(DIFFICULTY_SUBJECT_DIMENSION_ID)
        difficulty_subject_dimension_index = difficulty_subject_dimension_cid_list.index(
            difficult_dimension_cid) + 1

        question = {
            'id': subject.cid,
            'title': subject.title,
            'picture_url': title_picture_url,
            'category_name': category_subject_dimension.title if category_subject_dimension else '',
            'timeout': 20,
            'difficulty_degree': f'{difficulty_subject_dimension_index}/{difficulty_count}',
            'is_current': is_current,
            'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
            'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
            'resolving': subject.resolving
        }
        option_doc_list = subject.option_list
        option_list = []
        for option_doc in option_doc_list:
            option = {
                'id': option_doc.cid,
                'title': option_doc.title,
                'true_answer': option_doc.correct if option_doc.correct else False,
            }
            option_list.append(option)
        question['option_list'] = option_list

        return question
    return {}


async def do_diamond_reward(member: Member, source_diamond, diamond=None):
    if not isinstance(member, Member):
        raise ValueError('Parameter member_cid must be a type of Member.')
    if source_diamond not in SOURCE_MEMBER_DIAMOND_LIST:
        raise ValueError('Parameter source_diamond must in %s.' % str(SOURCE_MEMBER_DIAMOND_LIST))
    if diamond and not isinstance(diamond, (int, float)):
        raise TypeError('Parameter diamond must be type of int or float.')
    m_diamond = diamond
    if diamond is None:
        diamond_reward_obj = await GameDiamondReward.find_one(filtered={'source': source_diamond})
        if diamond_reward_obj:
            m_diamond = diamond_reward_obj.quantity
    if not m_diamond:
        m_diamond = 0

    member.diamond = member.diamond + m_diamond
    member.updated_dt = datetime.datetime.now()

    diamond_detail = MemberDiamondDetail()
    diamond_detail.member_cid = member.cid
    diamond_detail.diamond = m_diamond
    diamond_detail.source = source_diamond
    diamond_detail.reward_datetime = datetime.datetime.now()
    diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)

    await diamond_detail.save()
    await member.save()

    return True, m_diamond


async def deal_with_own_answers(member, own_answers):
    """
    处理小程序提交答案
    :param member:
    :param own_answers:
    :return:
    """

    unlock = False

    answers = own_answers.get('answers', [])  # 答题数据
    pk_status = own_answers.get('pk_status')  # pk结果
    runaway_index = own_answers.get('runaway_index', '')  # 逃跑题目
    score = own_answers.get('score', 0)
    dan_grade_index = own_answers.get('dan_grade_index')

    answer_list = []
    question_accuracy = {}
    for answer in answers:
        temp_answer = {}
        if answer:
            question_id = answer.get('question_id')
            temp_answer = {
                'subject_cid': answer.get('question_id'),
                'selected_option_cid': answer.get('option_id'),
                'consume_time': 20 - int(answer.get('remain_time', 0)),
                'score': int(answer.get('score', 0)),
                'true_answer': answer.get('true_answer')
            }
            if dan_grade_index:
                set_cached_subject_accuracy(question_id, answer.get('true_answer'))
            correct, error = get_cached_subject_accuracy(question_id)
            all_amount = correct + error
            percent = format(float(correct) / float(all_amount), '.2%') if all_amount else '0%'
            question_accuracy[question_id] = percent
        answer_list.append(temp_answer)

        await subject_wrong_statistics(answer, member.cid)
    # 保存答题历史
    continuous_win_times = 0
    member_game_history = None
    if dan_grade_index:
        member_game_history = MemberGameHistory()
        member_game_history.member_cid = member.cid
        member_game_history.result = answer_list
        member_game_history.status = int(pk_status)
        member_game_history.score = int(score)
        member_game_history.dan_grade = dan_grade_index
        member_game_history.fight_datetime = datetime.datetime.now()
        member_game_history.runaway_index = int(runaway_index) if runaway_index else None
        # 判断胜负以及解锁
        if member_game_history.status == STATUS_RESULT_GAME_PK_WIN:
            # 判断解锁
            current_dan_grade = member.dan_grade
            if current_dan_grade is None:
                current_dan_grade = TYPE_DAN_GRADE_ONE
            current_star_grade = member.star_grade
            if current_star_grade is None:
                current_star_grade = TYPE_STAR_GRADE_ONE
            else:
                current_star_grade += 1

            dan_grade_full_stars = DAN_STAR_GRADE_MAPPING.get(current_dan_grade)
            # 答题段位和当前段位一致，且满星了
            if dan_grade_index == current_dan_grade and current_star_grade >= dan_grade_full_stars:
                unlock = True
            # 判断连胜
            # 当前连胜次数
            last_pk_list = await MemberGameHistory.find({'member_cid': member.cid}).sort(
                [('fight_datetime', -1)]).limit(1).to_list(1)
            if last_pk_list and last_pk_list[0].continuous_win_times:
                member_game_history.continuous_win_times = last_pk_list[0].continuous_win_times + 1
            else:
                member_game_history.continuous_win_times = 1
        else:
            member_game_history.continuous_win_times = 0
        continuous_win_times = member_game_history.continuous_win_times  # 当前连胜

        await member_game_history.save()

        # 统计会员记录
        # await start_docking_statistics(member_game_history, member)

        start_accurate_statistics.delay(member_game_history, member)
        await start_dashboard_report_statistics(member_game_history, member)
        task_robot_analysis_reference_statistics.delay(member_game_history, member)

    return int(pk_status), unlock, continuous_win_times, question_accuracy, member_game_history


async def subject_wrong_statistics(answer, member_cid):
    """
    记录错题信息
    :param answer:答案
    :param member_cid:用户cid
    :return:
    """
    true_answer = answer.get('true_answer')
    if true_answer is False:
        subject_cid = answer.get('question_id')
        selected_option_cid = answer.get('option_id')
        member_wrong_subject = await MemberWrongSubject.find(
            dict(member_cid=member_cid, subject_cid=subject_cid, option_cid=selected_option_cid)).to_list(None)
        if member_wrong_subject:
            await MemberWrongSubject.delete_many({
                'member_cid': member_cid,
                'subject_cid': subject_cid,
                'option_cid': selected_option_cid
            })
        member_wrong_subject = MemberWrongSubject(member_cid=member_cid, subject_cid=subject_cid,
                                                  option_cid=selected_option_cid)
        member_wrong_subject.wrong_dt = datetime.datetime.now()
        await member_wrong_subject.save()
    elif true_answer is True:
        selected_option_cid = answer.get('option_id')
        subject_cid = answer.get('question_id')
        member_wrong_subject_list = await MemberWrongSubject.find(
            dict(member_cid=member_cid, subject_cid=subject_cid)).to_list(None)
        if member_wrong_subject_list:
            for member_wrong_subject in member_wrong_subject_list:
                member_wrong_subject.option_cid = selected_option_cid
                member_wrong_subject.status = STATUS_WRONG_SUBJECT_INACTIVE
                await member_wrong_subject.save()


def instance_member_diamond_detail(member_cid, diamond, source_diamond):
    """
    实例化用户钻石奖励详情
    :param member_cid: 用户CID
    :param diamond: 奖励钻石数
    :param source_diamond: 奖励类型
    :return:实例
    """
    diamond_detail = MemberDiamondDetail()
    diamond_detail.member_cid = member_cid
    diamond_detail.diamond = diamond
    diamond_detail.source = source_diamond
    diamond_detail.reward_datetime = datetime.datetime.now()
    diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)
    return diamond_detail


async def pk_award(member, pk_status, continuous_win_times):
    """
    处理pk钻石奖励
    首次PK，首次获胜，连胜奖励

    处理pk积分奖励
    首次pk 每日首次
    :param member:
    :param pk_status:
    :param continuous_win_times:
    :return:
    """
    total_diamond_reward = 0
    first_fight_amount = 0
    first_fight_win_amount = 0
    continuous_win_amount = 0
    total_integral_reward = None
    diamond_reward_info = []
    diamond_detail_list = []
    game_diamond_reward_dict = {}
    source_list = [SOURCE_MEMBER_DIAMOND_FIRST_PK, SOURCE_MEMBER_DIAMOND_FIRST_WIN,
                   SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START,
                   SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND]
    game_diamond_reward_cursor = GameDiamondReward.find(dict(source={'$in': source_list}))
    while await game_diamond_reward_cursor.fetch_next:
        game_diamond_reward = game_diamond_reward_cursor.next_object()
        if game_diamond_reward:
            game_diamond_reward_dict[game_diamond_reward.source] = game_diamond_reward

    # 判断是否首次pk
    fight_times = await MemberGameHistory.count(filtered={'member_cid': member.cid},
                                                read_preference=ReadPreference.PRIMARY)
    if fight_times == 1:
        # 钻石
        first_pk_reward = game_diamond_reward_dict.get(SOURCE_MEMBER_DIAMOND_FIRST_PK)
        total_diamond_reward += (first_pk_reward.quantity if first_pk_reward else 0)
        first_fight_amount = first_pk_reward.quantity if first_pk_reward else 0  # 首次PK奖励钻石数
        diamond_detail = instance_member_diamond_detail(member.cid, first_fight_amount, SOURCE_MEMBER_DIAMOND_FIRST_PK)
        diamond_detail_list.append(diamond_detail)
    # 判断是否首次获胜
    if fight_times == 1 and pk_status == STATUS_RESULT_GAME_PK_WIN:
        # 首次获胜钻石奖励
        first_win_reward = game_diamond_reward_dict.get(SOURCE_MEMBER_DIAMOND_FIRST_WIN)
        total_diamond_reward += (first_win_reward.quantity if first_win_reward else 0)
        first_fight_win_amount = first_win_reward.quantity if first_win_reward else 0
        diamond_detail = instance_member_diamond_detail(member.cid, first_fight_win_amount,
                                                        SOURCE_MEMBER_DIAMOND_FIRST_WIN)
        diamond_detail_list.append(diamond_detail)
    # 判断连胜
    # 起始次数
    win_streak_reward = game_diamond_reward_dict.get(SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES)
    if not win_streak_reward or not win_streak_reward.quantity:
        start_times = 0
    else:
        start_times = win_streak_reward.quantity
    if start_times is not None and continuous_win_times >= start_times:
        # 起始奖励钻石
        start_award_obj = game_diamond_reward_dict.get(SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START)
        if not start_award_obj or not start_award_obj.quantity:
            start_award = 0
        else:
            start_award = start_award_obj.quantity
        # 每次连胜增加钻石
        every_award_obj = game_diamond_reward_dict.get(SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND)
        if not every_award_obj:
            every_award = 0
        else:
            every_award = every_award_obj.quantity

        reward_diamond = start_award + (continuous_win_times - start_times) * every_award
        diamond_detail = instance_member_diamond_detail(member.cid, reward_diamond,
                                                        SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND)
        diamond_detail_list.append(diamond_detail)
        total_diamond_reward += (reward_diamond if reward_diamond else 0)
        continuous_win_amount = reward_diamond
    # 用户奖励钻石记录
    member.diamond = member.diamond + total_diamond_reward
    await member.save()
    await MemberDiamondDetail.insert_many(diamond_detail_list)
    return total_diamond_reward, first_fight_amount, first_fight_win_amount, continuous_win_amount


async def update_member_pk_info(member, pk_status, unlock, grade_id):
    """
    根据pk结果来更新用户的pk信息
    :param member:
    :param pk_status:
    :param unlock:
    :param grade_id:
    :return:
    """
    fight_times = int(member.fight_times) + 1 if member.fight_times else 1
    win_times = int(member.win_times) + 1 if member.win_times else 1
    win_percent = float(win_times / fight_times)

    member.fight_times = fight_times
    member.win_times = win_times
    member.win_percent = win_percent
    member.updated_dt = datetime.datetime.now()

    diamond_changes = 0  # 钻石相关
    current_star_diamond = member.diamond
    diamond_consume_obj = await GameDiamondConsume.find_one(filtered={'source': grade_id})
    diamond_consume = diamond_consume_obj.quantity

    current_star_grade = member.star_grade if member.star_grade else 0  # 当前星级
    current_dan_grade = member.dan_grade
    if pk_status == STATUS_RESULT_GAME_PK_WIN:
        if unlock:  # 段位 + 1
            if current_dan_grade:
                if current_dan_grade < TYPE_DAN_GRADE_ELEVEN:
                    member.dan_grade = current_dan_grade + 1
                    member.star_grade = 0
                else:
                    if current_star_grade < DAN_STAR_GRADE_MAPPING.get(current_dan_grade):
                        member.star_grade = current_star_grade + 1
            else:
                member.dan_grade = TYPE_DAN_GRADE_ONE
        else:
            # 答题段位是当前段位时，星级 + 1，否则不加
            if current_dan_grade == grade_id:
                member.star_grade = current_star_grade + 1  # 星级 + 1
        # 增加钻石
        diamond_changes = diamond_consume  # 返回钻石为入场费
        member.diamond = current_star_diamond + (diamond_consume * 2)  # 实际钻石更新为两倍
        # 更新钻石奖励历史
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, diamond_consume)
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_VICTORY, diamond_consume)
    elif pk_status in [STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP]:
        # 星星数扣减
        # if current_dan_grade == grade_id:
        #     member.star_grade = current_star_grade - 1 if current_star_grade else 0  # 星级-1
        # 扣除钻石，实际已经处理
        diamond_changes = diamond_consume
    elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
        # 返还入场费
        member.diamond = current_star_diamond + diamond_consume
        # 更新钻石奖励历史
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, diamond_consume)

    pk_history_list = await MemberGameHistory.find({
        'member_cid': member.cid,
        'continuous_win_times': {'$ne': None}
    }).sort([('continuous_win_times', DESC)]).limit(1).to_list(1)

    pk_history = None
    if pk_history_list:
        pk_history = pk_history_list[0]

    continuous_win_times = pk_history.continuous_win_times if pk_history else 0  # 最大连胜
    current_highest_win_times = member.highest_win_times
    if not current_highest_win_times or (
            current_highest_win_times and current_highest_win_times < continuous_win_times):
        member.highest_win_times = continuous_win_times
    await member.save()
    return diamond_changes


async def get_member_ranking_list(member, period=None, find_area=False, find_time=False,
                                  q_member_cid_list: list = None):
    """
    查询会员排行榜
    :param member: 会员
    :param period: 周期
    :param find_area: 是否为区域查询
    :param find_time: 是否为周期内查询
    :param q_member_cid_list: 好友排行查询
    :return:
    """
    query = {'quantity': {'$ne': 0}}

    if find_time:
        current_datetime = datetime.datetime.now()
        start_datetime = current_datetime - datetime.timedelta(days=period)
        query["award_dt"] = {'$gte': start_datetime, '$lte': current_datetime}

    if q_member_cid_list:
        query['member_cid'] = {'$in': q_member_cid_list}

    group_stage = GroupStage('member_cid', quantity={'$sum': '$quantity'}, dan_grade={'$max': '$dan_grade'})
    sort_stage = SortStage([('dan_grade', DESC), ('quantity', DESC)])

    match_lookup_list = [{'$eq': ['$cid', '$$member_cid']}, ]
    if find_area:
        match_lookup_list.append({'$eq': ['$city_code', member.city_code]})
    lookup_stage = LookupStage(
        Member,
        as_list_name='member_info',
        let={'member_cid': '$_id'},
        pipeline=[
            MatchStage({
                '$expr': {
                    '$and': match_lookup_list
                }
            }),
        ])

    project_stage = ProjectStage(**{
        'cid': '$_id',
        'dan_grade': '$dan_grade',
        'nick_name': {'$arrayElemAt': ['$member_info.nick_name', 0]},
        'avatar': {'$arrayElemAt': ['$member_info.avatar', 0]},
        'quantity': '$quantity'})

    member_info_stage = MatchStage({'$and': [{'member_info': {'$ne': []}}]})
    stage_list = [MatchStage(query), group_stage, sort_stage, lookup_stage, member_info_stage, LimitStage(30),
                  project_stage]

    member_cursor = MemberStarsAwardHistory.aggregate(stage_list)
    rankings = []
    member_cid_list = []
    while await member_cursor.fetch_next:
        temp_member = member_cursor.next_object()
        if temp_member:
            rankings.append({
                'nick_name': temp_member.nick_name,
                'avatar': temp_member.avatar,
                'all_stars': temp_member.quantity if temp_member.quantity else 0,
                'dan_grade': await get_dan_grade_by_index(temp_member.dan_grade)
            })
            member_cid_list.append(temp_member.cid)
    if member.cid in member_cid_list:
        my_ranking = member_cid_list.index(member.cid) + 1
    else:
        member_award = await MemberStarsAwardHistory.aggregate([
            MatchStage(dict(member_cid=member.cid)),
            GroupStage('member_cid', count={'$sum': '$quantity'})]).to_list(None)
        if not member_award:
            my_ranking = 0
        else:
            member_cid_list = await MemberStarsAwardHistory.aggregate([
                MatchStage(query), group_stage, sort_stage, lookup_stage, member_info_stage,
                project_stage, MatchStage({'dan_grade': {'$gte': member.dan_grade}})
            ]).to_list(None)

            my_ranking = len(member_cid_list)

    return rankings, my_ranking


async def get_dimension_cid(code=None):
    if not code:
        raise ValueError('Parameter[code] is missing.')

    dimension_cid = RedisCache.get(code)
    if not dimension_cid:
        dimension = await SubjectDimension.find_one({'code': code})
        if dimension:
            dimension_cid = dimension.cid
            RedisCache.set(code, dimension_cid)

    return dimension_cid


async def convert_subject_dimension_dict(dimension_dict: dict):
    """

    :param dimension_dict:
    :return:
    """
    dimension_list = await SubjectDimension.aggregate(stage_list=[
        MatchStage({'cid': {"$in": [v for _, v in dimension_dict.items()]}}),
        LookupStage(SubjectDimension, 'parent_cid', 'cid', 'parent_list')
    ]).to_list(None)

    return {dimension.parent_list[0].title: dimension for dimension in dimension_list}


async def async_request(url, method='GET', data=None, **kwargs):
    """
    异步发起GET请求
    :param url:
    :param method
    :param data:
    :param kwargs:
    :return:
    """

    async with aiohttp.ClientSession() as session:
        func = getattr(session, method.lower())
        if not func:
            raise ValueError('method [%s] is not allowed. ' % method)
        async with func(url, data=data, **kwargs) as res:
            return await res.text()


async def is_redpacket_enabled(check_point: RaceGameCheckPoint):
    """

    :param check_point:
    :return:
    """
    if not check_point:
        raise ValueError('check_point can not be None.')

    race = await Race.find_one({'cid': check_point.race_cid})
    if not race.redpkt_start_dt or not race.redpkt_end_dt:
        return False

    if race.redpkt_start_dt >= race.redpkt_end_dt:
        return False

    if race.redpkt_end_dt <= datetime.datetime.now():
        return False

    redpkt_rule = await RedPacketRule.find_one({'cid': check_point.redpkt_rule_cid, 'status': STATUS_ACTIVE})
    if not redpkt_rule:
        return False

    return True


def deal_param(url, method: str = 'GET', redpkt_account: str = None, **kwargs):
    """

    :param url:
    :param method:
    :param redpkt_account:
    :param kwargs:
    :return:
    """

    params = {
        'project_id': REDPACKET_PLATFORM_PROJECT_ID,
        'redpkt_id': redpkt_account,
        'ts': int(time.time())
    }
    for key, value in kwargs.items():
        params[key] = value
    params_str = json.dumps(params, separators=(',', ':'), sort_keys=True, ensure_ascii=False)

    sha_string = (method.upper() + url + params_str + REDPACKET_PLATFORM_SECRECT_KEY).encode('utf-8')
    v = hashlib.sha1(sha_string).hexdigest()
    params['v'] = v

    return params


def generate_rid(race_cid: str, member_cid: str, redpacket_cid: str):
    """

    :param race_cid:
    :param member_cid:
    :param redpacket_cid:
    :return:
    """
    if not (race_cid and member_cid and redpacket_cid):
        raise Exception('There is not redpacket_cid.')

    return '%s-%s-%s' % (race_cid, member_cid, redpacket_cid)


def parse_rid(rid: str):
    """
    解析rid
    :param rid:
    :return:
    """
    if not rid:
        raise Exception('There is not rid.')

    if isinstance(rid, bytes):
        rid = rid.decode('utf-8')

    return rid.split('-')


async def get_lottery_table(rule_cid):
    """

    :param rule_cid:
    :return:
    """
    item_json = RedisCache.hget(KEY_CACHE_LOTTERY_TABLE, rule_cid)
    if item_json:
        item_json = json.loads(item_json.decode(encoding="utf-8"))
        item_table = item_json.get('item_table')
        err_index = item_json.get('err_index')
    else:
        item_list = await RedPacketItemSetting.aggregate([
            MatchStage({'rule_cid': rule_cid, 'record_flag': 1}),
            SortStage([('amount', DESC)])
        ]).to_list(None)

        item_table = [item.title for item in item_list]

        fail_msg = '谢谢参与'
        i, err_index = 0, -1
        while len(item_table) < 6:
            item_table.insert(1 + i, fail_msg)
            i += 2

        try:
            err_index = item_table.index(fail_msg)
        except ValueError:
            pass
        RedisCache.hset(KEY_CACHE_LOTTERY_TABLE, rule_cid,
                        json.dumps({'item_table': item_table, 'err_index': err_index}))
    return item_table, err_index


def add_notice(member_cid=None, race_cid=None, checkpoint_cid=None, msg_type: int = None,
               redpkt_box: RedPacketBox = None):
    """
    增加中奖通知
    :param member_cid:
    :param race_cid:
    :param checkpoint_cid:
    :param msg_type:
    :param redpkt_box:
    :return:
    """

    notice = MemberNotice.sync_find_one(
        {'member_cid': member_cid, 'checkpoint_cid': checkpoint_cid, 'needless.msg_type': msg_type, 'record_flag': 1})
    if notice:
        return

    notice = MemberNotice()
    notice.member_cid = member_cid
    notice.race_cid = race_cid
    notice.checkpoint_cid = checkpoint_cid
    notice.category = CATEGORY_NOTICE_AWARD

    race = Race.sync_get_by_cid(race_cid)
    checkpoint = RaceGameCheckPoint.sync_get_by_cid(checkpoint_cid)
    msg = "[{0}活动-{1}] {2}"
    content = ""
    if msg_type == TYPE_MSG_LOTTERY:
        content = "获得一次抽奖机会。"

    if msg_type == TYPE_MSG_DRAW:
        content = redpkt_box.award_msg

    notice.content = msg.format(race.title, checkpoint.alias, content)
    notice.needless['msg_type'] = msg_type
    notice.sync_save()


async def async_add_notice(member_cid=None, race_cid=None, checkpoint_cid=None, msg_type: int = None,
                           redpkt_box: RedPacketBox = None):
    """
    增加中奖通知
    :param member_cid:
    :param race_cid:
    :param checkpoint_cid:
    :param msg_type:
    :param redpkt_box:
    :return:
    """

    notice = await MemberNotice.find_one(
        {'member_cid': member_cid, 'checkpoint_cid': checkpoint_cid, 'needless.msg_type': msg_type, 'record_flag': 1})
    if notice:
        return

    notice = MemberNotice()
    notice.member_cid = member_cid
    notice.race_cid = race_cid
    notice.checkpoint_cid = checkpoint_cid
    notice.category = CATEGORY_NOTICE_AWARD

    race = await Race.get_by_cid(race_cid)
    checkpoint = await RaceGameCheckPoint.get_by_cid(checkpoint_cid)
    msg = "[{0}活动-{1}] {2}"
    content = ""
    if msg_type == TYPE_MSG_LOTTERY:
        content = "获得一次抽奖机会。"

    if msg_type == TYPE_MSG_DRAW:
        content = redpkt_box.award_msg

    notice.content = msg.format(race.title, checkpoint.alias, content)
    notice.needless['msg_type'] = msg_type
    await notice.save()


async def clear_lottery_notice(member_cid, checkpoint_cid):
    """
    消除抽奖通知
    :param member_cid:
    :param checkpoint_cid:
    :return:
    """
    lottery_notice_list = await MemberNotice.find(
        {'member_cid': member_cid, 'checkpoint_cid': checkpoint_cid,
         'needless.msg_type': TYPE_MSG_LOTTERY}).to_list(None)

    for no in lottery_notice_list:
        no.status = STATUS_NOTICE_READ
        await no.save()
