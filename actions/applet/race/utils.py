import datetime
import math
import random

from actions.applet.utils import get_dimension_cid
from caches.redis_utils import RedisCache
from db import TYPE_AGE_GROUP_NONE, TYPE_AGE_GROUP_YOUNG, TYPE_AGE_GROUP_MIDDLE, TYPE_AGE_GROUP_OLD, \
    TYPE_EDUCATION_NONE, TYPE_EDUCATION_JUNIOR, TYPE_EDUCATION_SENIOR, TYPE_EDUCATION_COLLEGE, TYPE_EDUCATION_BACHELOR, \
    TYPE_EDUCATION_MASTER, SEX_NONE, SEX_MALE, SEX_FEMALE, SEX_LIST, TYPE_AGE_GROUP_LIST, TYPE_EDUCATION_LIST, \
    MAX_RESPOND_SECONDS, STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_RESULT_CHECK_POINT_WIN, STATUS_INACTIVE, \
    KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT
from db.models import Member, RaceSubjectBanks, UploadFiles, RaceSubjectRefer, SubjectOption, \
    FightRobotAnalysisReference, SubjectDimension, MemberCheckPointHistory, RaceGameCheckPoint, Subject, RedPacketRule, \
    Race
from enums import KEY_PREFIX_SUBJECT_BANKS_COUNT
from motorengine import ASC, FacadeO, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, ProjectStage
from motorengine.stages.group_stage import GroupStage
from settings import STATIC_URL_PREFIX, SERVER_PROTOCOL, SERVER_HOST

DEFAULT_WORDS = 64
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


async def do_get_suite_subject_list(race_cid: str, rule_cid: str, member: Member = None):
    """
    获取套题
    :param race_cid: 竞赛活动cid
    :param rule_cid:
    :param member:
    :return:
    """
    try:
        subject_list = await do_get_suite_subject_and_set_robot_info(race_cid, rule_cid, member)
        if not subject_list:
            raise AttributeError('No subject returned.')
    except AttributeError:
        subject_list = await do_get_suite_subject_and_set_robot_info(race_cid, rule_cid, member)
    return subject_list


async def do_get_suite_subject_and_set_robot_info(race_cid: str, rule_cid: str, member: Member = None):
    """
    填充套题机器人信息
    :param rule_cid:抽题规则cid
    :param race_cid:竞赛活动cid
    :param member:
    :return:
    """
    if rule_cid and race_cid:
        race_subject_list = await do_query_fight_subjects_by_rule_oid(race_cid, rule_cid)
        if race_subject_list:
            race_subject_cid_list = [subject.cid for subject in race_subject_list]
            if race_subject_cid_list:
                kwargs = {}
                if member:
                    if member.sex is not None:
                        kwargs['gender'] = member.sex
                    if member.age_group is not None:
                        kwargs['age_group'] = member.age_group
                    if member.education is not None:
                        kwargs['education'] = member.education
                stat_data: dict = await do_get_subject_analysis_stat_data(race_subject_cid_list, **kwargs)
                for subject in race_subject_list:
                    do_set_subject_robot_info(subject, stat_data, member)
                return race_subject_list
    return []


async def do_query_fight_subjects_by_rule_oid(race_cid: str, rule_cid: str):
    """
    依据抽题规则oid查询题目
    :param race_cid:
    :param rule_cid:
    :return:
    """
    if rule_cid and rule_cid:
        count = await get_subject_bank_quantity(race_cid, rule_cid)
        if count > 0:
            # 获取题目
            race_subject_bank_list = await RaceSubjectBanks.find(
                dict(rule_cid=rule_cid, race_cid=race_cid, record_flag=1)).skip(
                random.randint(1, count - 1)).limit(1).to_list(1)
            if race_subject_bank_list:
                race_subject_bank = await RaceSubjectBanks.find_one({'cid': race_subject_bank_list[0].cid})
                # subject_id_list = [ObjectId(subject_id) if isinstance(subject_id, str) else subject_id
                #                    for subject_id in subject_bank.subject_id_list]
                race_subject_cid = [subject_cid for subject_cid in race_subject_bank.refer_subject_cid_list]
                race_subject_list = await RaceSubjectRefer.aggregate(stage_list=[
                    MatchStage({'cid': {'$in': race_subject_cid}, 'race_cid': race_cid}),
                    LookupStage(SubjectOption, let={'sub_cid': '$subject_cid'},
                                pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$sub_cid']}]}}},
                                          SortStage([('code', ASC)])], as_list_name='option_list'),
                    LookupStage(Subject, 'subject_cid', 'cid', 'subject_list'),
                    ProjectStage(**{
                        'race_cid': '$race_cid',
                        'subject_cid': '$subject_cid',
                        'title': '$title',
                        'status': '$status',
                        'choice': '$choice',
                        'dimension_dict': '$dimension_dict',
                        'option_list': '$option_list',
                        'image_cid': {'$arrayElemAt': ['$subject_list.image_cid', 0]}
                    }),
                    LookupStage(UploadFiles, 'image_cid', 'cid', 'image_list')
                ]).to_list(None)
                return race_subject_list
    return None


async def get_subject_bank_quantity(race_cid: str, rule_cid: str):
    """
    获取题库套数
    :param rule_cid: 抽题规则cid
    :param race_cid:竞赛活动cid
    :return:
    """
    # 获取题目数量
    cache_key = '%s_%s' % (KEY_PREFIX_SUBJECT_BANKS_COUNT, rule_cid)
    count = RedisCache.get(cache_key)
    if count is None:
        count = await RaceSubjectBanks.count(dict(rule_cid=rule_cid, race_cid=race_cid, record_flag=1))
        RedisCache.set(cache_key, count)
    return int(count)


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


async def do_get_subject_analysis_stat_data(race_subject_cid_list, gender=None, age_group=None, education=None):
    """
    获取机器题目分析统计数据
    :param race_subject_cid_list:
    :param gender:
    :param age_group:
    :param education:
    :return:
    """
    if race_subject_cid_list:
        data = {}
        match_dict = {'subject_cid': {'$in': race_subject_cid_list}}
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
        accuracy = do_get_subject_final_accuracy(robot_data.get('accuracy', random.random()), member)

        is_correct = do_judge_subject_correctness(accuracy)
        if is_correct:
            stat_seconds = robot_data.get('correct_seconds', random.randint(0, 3))
        else:
            stat_seconds = robot_data.get('incorrect_seconds', random.randint(3, 6))

        seconds = do_get_subject_final_seconds(stat_seconds, words, member)

        # 设置属性
        setattr(subject, 'is_correct', is_correct)
        setattr(subject, 'answer_seconds', seconds)

        correct_option_oid = None
        incorrect_option_oid_list = []

        option_list = subject.option_list
        for index, option in enumerate(option_list):
            fo = FacadeO(option)
            subject.option_list[index] = fo
            if fo:
                if fo.correct:
                    correct_option_oid = fo.oid
                else:
                    incorrect_option_oid_list.append(fo.oid)
        if is_correct:
            setattr(subject, 'choice_option_id', correct_option_oid)
        else:
            setattr(subject, 'choice_option_id', random.choice(incorrect_option_oid_list))


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


async def deal_subject_list(race_cid, race_subject_list: list):
    """
    处理获取到的竞赛活动关卡题目
    :param race_subject_list:
    :param race_cid:
    :return:
    """
    question_list = []
    answer_list = []
    subject_list = []
    race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
    for race_subject in race_subject_list:
        subject = await Subject.find_one({'cid': race_subject.subject_cid, 'record_flag': 1})
        if subject:
            subject_list.append(subject)
    if race_subject_list:
        for index, subject in enumerate(race_subject_list):
            title_picture_url = ''
            if subject.image_list:
                title_picture = subject.image_list[0].title
                if title_picture:
                    title_picture_url = '%s://%s%s%s%s' % (
                        SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', title_picture)

            difficulty_cid = await get_dimension_cid(code='CSD001')
            difficulty_child_cid = subject.dimension_dict.get(difficulty_cid)
            difficulty = await SubjectDimension.get_by_cid(difficulty_child_cid)
            difficulty_degree = difficulty.ordered
            category_cid = await get_dimension_cid(code='CSK001')
            category_child_cid = subject.dimension_dict.get(category_cid)
            category = await SubjectDimension.get_by_cid(category_child_cid)
            category_name = category.title
            question_dict = {
                'id': subject.subject_cid,
                'title': subject.title,
                'picture_url': title_picture_url,
                'timeout': 20,
                'difficulty_degree': str(difficulty_degree) + '/' + '5',
                'category_name': category_name,
                'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject_list[index].knowledge_first) if race else '',
                'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(
                    subject_list[index].knowledge_second) if race else '',
                'resolving': subject_list[index].resolving if race else '',
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
                'question_id': subject.oid,
                'option_id': subject.choice_option_id,
                'true_answer': subject.is_correct
            }
            answer_list.append(answer_dict)
    return question_list, answer_list


async def is_stage_clear(member: Member, race_cid: str):
    """

    :param member:
    :param race_cid:
    :return:
    """
    race_checkpoints = await RaceGameCheckPoint.find(
        {'status': STATUS_GAME_CHECK_POINT_ACTIVE, 'race_cid': race_cid}).sort(
        [('index', DESC)]).to_list(None)

    checkpoint_history = await MemberCheckPointHistory.find_one(
        filtered={'member_cid': member.cid, 'check_point_cid': race_checkpoints[0].cid,
                  'status': STATUS_RESULT_CHECK_POINT_WIN, 'record_flag': 1})
    if checkpoint_history:
        return True
    return False


async def has_redpkt(race_cid, checkpoint: RaceGameCheckPoint, member_cid):
    """
    检查关卡是否还有红包可以领取
    :param race_cid:
    :param checkpoint:
    :param member_cid:
    :return:
    """
    if not checkpoint.redpkt_rule_cid:
        return False

    rule = await RedPacketRule.get_by_cid(checkpoint.redpkt_rule_cid)
    if rule.status == STATUS_INACTIVE:
        return False
    race = await Race.find_one({'cid': race_cid, 'record_flag': 1})
    history = await MemberCheckPointHistory.find_one(
        {'check_point_cid': checkpoint.cid, 'member_cid': member_cid, 'status': STATUS_RESULT_CHECK_POINT_WIN,
         'record_flag': 1})
    if race.redpkt_end_dt:
        if not history and race.redpkt_end_dt > datetime.datetime.now() > race.redpkt_start_dt:
            return True

    return False
