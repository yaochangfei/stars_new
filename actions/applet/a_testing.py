#! /usr/bin/python

import datetime
import traceback

from actions.applet import find_member_by_open_id
from db import STATUS_USER_ACTIVE, STATUS_SUBJECT_ACTIVE, CATEGORY_SUBJECT_BENCHMARK, \
    CATEGORY_SUBJECT_KNOWLEDGE_DICT, KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT, \
    CATEGORY_SUBJECT_GRADUATION, CATEGORY_EXAM_CERTIFICATE_PRIMARY, CATEGORY_EXAM_CERTIFICATE_ADVANCED, \
    CATEGORY_EXAM_CERTIFICATE_SUPER
from db.models import Member, Subject, MemberWrongSubject, SubjectOption, MemberExamHistory, UploadFiles, \
    MemberExamCertificate
from logger import log_utils
from motorengine import ASC
from motorengine.stages import MatchStage, SortStage, LookupStage
from settings import SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX
from tornado.web import url
from web import decorators, WechatAppletHandler

logger = log_utils.get_logging('a_testing')


class AppletTestingQuestionsHandler(WechatAppletHandler):
    """获取基准测试或毕业测试题目"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        category = self.get_i_argument('category', None)
        if not category or (int(category) not in [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]):
            return r_dict

        try:
            stage_list = [
                MatchStage({'category_use': int(category), 'status': STATUS_SUBJECT_ACTIVE}),
                LookupStage(SubjectOption, let={'cid': '$cid'},
                            pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                      SortStage([('code', ASC)])], as_list_name='option_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'image_list'),
                SortStage([('code', ASC)])
            ]

            subjects = await Subject.aggregate(stage_list=stage_list).to_list(None)
            question_list = []
            for sbj in subjects:
                picture_url = ''
                if sbj.image_list:
                    picture_url = '%s://%s%s%s%s' % (
                        SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', sbj.image_list[0].title)

                question = {'id': sbj.cid,
                            'title': sbj.title,
                            'picture_url': picture_url,
                            'category_name': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(sbj.category, ''),
                            'difficulty_degree': "%s/5" % sbj.difficulty,
                            'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(sbj.knowledge_first, ''),
                            'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(sbj.knowledge_second, ''),
                            'resolving': sbj.resolving,
                            'option_list': [{
                                'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct
                            } for opt in sbj.option_list]}

                question_list.append(question)

            r_dict = {
                'code': 1000,
                'question_list': question_list
            }
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


class AppletTestingAnswersSaveHandler(WechatAppletHandler):
    """保存基准测试&毕业测试结果"""

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        open_id = self.get_i_argument('open_id')
        if not open_id:
            r_dict['code'] = 1001
            return r_dict
        try:
            member = await find_member_by_open_id(open_id)
            if not member:
                r_dict['code'] = 1002
                return r_dict

            answers = self.get_i_argument('answers')
            remain_time = self.get_i_argument('remain_time')
            category = self.get_i_argument('category')
            question_quantity = self.get_i_argument('question_quantity')
            correct_quantity = self.get_i_argument('correct_quantity')

            if not category or (int(category) not in [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]):
                logger.error('Parameter(category) was incorrect.')
                return r_dict

            history = await MemberExamHistory.find_one({'member_cid': member.cid, 'category': int(category)})
            if not history:
                history = MemberExamHistory(member_cid=member.cid, category=int(category))

            accuracy = int(correct_quantity) / int(question_quantity)
            history.remain_time = remain_time
            history.exam_datetime = datetime.datetime.now()
            history.accuracy = accuracy
            await history.save()

            for answer in answers:
                if not answer.get('true_answer'):
                    wrong_sbj = await MemberWrongSubject.find_one(
                        {'member_cid': member.cid, 'subject_cid': answer.get('question_id')})
                    if not wrong_sbj:
                        wrong_sbj = MemberWrongSubject(member_cid=member.cid, subject_cid=answer.get('question_id'),
                                                       option_cid=answer.get('option_id'))

                    wrong_sbj.wrong_dt = history.exam_datetime

                    await wrong_sbj.save()

            if int(category) == CATEGORY_SUBJECT_GRADUATION:
                if correct_quantity < 6:
                    cert_category = CATEGORY_EXAM_CERTIFICATE_PRIMARY
                elif correct_quantity < 11:
                    cert_category = CATEGORY_EXAM_CERTIFICATE_ADVANCED
                else:
                    cert_category = CATEGORY_EXAM_CERTIFICATE_SUPER

                cert = await MemberExamCertificate.find_one(
                    dict(member_cid=member.cid, history_cid=history.cid, category=cert_category))
                if not cert:
                    cert = MemberExamCertificate(member_cid=member.cid, history_cid=history.cid, category=cert_category)

                cert.award_dt = datetime.datetime.now()
                await cert.save()
            r_dict = {'code': 1000, 'beyond_percent': await self.get_rank(accuracy, category)}
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict

    @staticmethod
    async def get_rank(accuracy, category):
        """

        :return:
        """
        count = await MemberExamHistory.count({'category': int(category)})
        if count == 0:
            return 100
        below_num = await MemberExamHistory.count({'category': int(category), 'accuracy': {'$lte': accuracy}})
        return int(below_num / count * 100)


class AppletTestingSubjectResolvingGetHandler(WechatAppletHandler):
    """
    获取答案解析
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        """

        :return:
        """
        question_list = []
        r_dict = {'code': 0, 'question_list': question_list}

        open_id = self.get_i_argument('open_id', None)
        if not open_id:
            return r_dict

        member = await find_member_by_open_id(open_id)
        question_ids = self.get_i_argument('question_ids', [])
        try:
            r_dict['code'] = 1000

            questions_wrong = await self.get_wrong_question(member.cid, question_ids)
            question_correct_ids = set(question_ids) ^ {q.get('id') for q in questions_wrong}

            questions_correct = list()
            if question_correct_ids:
                questions_correct = await self.get_correct_question(question_correct_ids)

            q_wrong_dict = {q.get('id'): q for q in questions_wrong}
            q_correct_dict = {q.get('id'): q for q in questions_correct}

            question_list = []
            for q_cid in question_ids:
                if q_cid in q_wrong_dict.keys():
                    question_list.append(q_wrong_dict.get(q_cid))
                elif q_cid in q_correct_dict.keys():
                    question_list.append(q_correct_dict.get(q_cid))
                else:
                    msg = 'some subject has missing , please check.'
                    logger.error(msg)
                    r_dict = {'code': 0, 'msg': msg}
                    return r_dict

            r_dict['question_list'] = question_list
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict

    @staticmethod
    async def get_correct_percent(subject_cid):
        """

        :param subject_cid:
        :return:
        """
        from random import randint
        return "%d%%" % randint(70, 99)

    async def get_wrong_question(self, member_id, question_ids):
        """

        :param member_id:
        :param question_id:
        :return:
        """
        stage_list = [
            MatchStage({'cid': {'$in': question_ids}}),
            LookupStage(SubjectOption, let={'cid': '$cid'},
                        pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                  SortStage([('code', ASC)])], as_list_name='options'),
            LookupStage(MemberWrongSubject, let={'cid': '$cid'}, as_list_name='wrong_subjects', pipeline=[
                {'$match': {
                    '$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}, {'$eq': ['$member_cid', member_id]}]}}}
            ]),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list'),
        ]

        subjects = await Subject.aggregate(
            stage_list=stage_list).to_list(None)

        if not subjects:
            return None

        questions = list()
        for subject in subjects:
            question = dict()
            question['id'] = subject.cid
            question['title'] = subject.title
            question['resolving'] = subject.resolving

            options = []
            for opt in subject.options:
                option = {'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct, }
                if subject.wrong_subjects[-1].option_cid == opt.cid:
                    option['show_false'] = 'option_false'
                else:
                    option['show_false'] = ''

                options.append(option)

            question['option_list'] = options
            question['category_name'] = CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category)
            question['knowledge_first'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first)
            question['knowledge_second'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_second)
            question['difficulty'] = subject.difficulty
            question['correct_percent'] = await self.get_correct_percent(subject.cid)

            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''

            question['picture_url'] = title_picture_url

            questions.append(question)
        return questions

    async def get_correct_question(self, question_ids):
        """

        :param question_id:
        :return:
        """
        stage_list = [
            MatchStage({'cid': {'$in': question_ids}}),
            LookupStage(SubjectOption, let={'cid': '$cid'},
                        pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                  SortStage([('code', ASC)])], as_list_name='options'),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list'),
        ]

        subjects = await Subject.aggregate(stage_list=stage_list).to_list(None)

        if not subjects:
            return None

        questions = list()
        for subject in subjects:
            question = dict()
            question['id'] = subject.cid
            question['title'] = subject.title
            question['resolving'] = subject.resolving

            options = []
            for opt in subject.options:
                options.append({'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct, 'show_false': ''})

            question['option_list'] = options
            question['category_name'] = CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category)
            question['knowledge_first'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first)
            question['knowledge_second'] = KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_second)
            question['difficulty'] = subject.difficulty
            question['correct_percent'] = await self.get_correct_percent(subject.cid)

            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''

            question['picture_url'] = title_picture_url

            questions.append(question)
        return questions


URL_MAPPING_LIST = [
    url(r'/wechat/applet/testing/questions/', AppletTestingQuestionsHandler, name='wechat_applet_testing_questions'),
    url(r'/wechat/applet/testing/answers/save/', AppletTestingAnswersSaveHandler,
        name='wechat_applet_testing_answers_save'),
    url(r'/wechat/applet/testing/subject/resolving/get/', AppletTestingSubjectResolvingGetHandler,
        name='wechat_applet_testing_subject_resolving_get')
]
