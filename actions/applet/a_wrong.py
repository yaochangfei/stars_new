#! /usr/bin/python


import traceback

from actions.applet import find_member_by_open_id
from tornado.web import url

from db import STATUS_USER_ACTIVE, STATUS_WRONG_SUBJECT_ACTIVE, KNOWLEDGE_FIRST_LEVEL_DICT, KNOWLEDGE_SECOND_LEVEL_DICT
from db.models import Member, MemberWrongSubject, Subject, SubjectOption, UploadFiles, SubjectWrongViewedStatistics, \
    SubjectDimension
from logger import log_utils
from motorengine import ASC, DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, LimitStage
from motorengine.stages.project_stage import ProjectStage
from settings import SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX
from web import WechatAppletHandler, decorators
from wechat.wechat_utils import get_cached_subject_accuracy

logger = log_utils.get_logging()


class AppletWrongQuestionsGetHandler(WechatAppletHandler):
    """获取答错题目信息(错题本)"""

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

            wrong_subjects = await MemberWrongSubject.aggregate([
                MatchStage({'member_cid': member.cid, 'status': STATUS_WRONG_SUBJECT_ACTIVE}),
                SortStage([('wrong_dt', DESC)]),
                LimitStage(10),
                LookupStage(Subject, 'subject_cid', 'cid', 'subject_list'),
                ProjectStage(**{
                    'dan_grade': {'$arrayElemAt': ['$member_info.dan_grade', 0]},
                    'cid': '$subject_cid',
                    'title': {'$arrayElemAt': ['$subject_list.title', 0]},
                    'dimension_dict': {'$arrayElemAt': ['$subject_list.dimension_dict', 0]},
                    'knowledge_first': {'$arrayElemAt': ['$subject_list.knowledge_first', 0]},
                    'knowledge_second': {'$arrayElemAt': ['$subject_list.knowledge_second', 0]},
                    'resolving': {'$arrayElemAt': ['$subject_list.resolving', 0]},
                    'option_cid': '$option_cid',
                    'image_cid': {'$arrayElemAt': ['$subject_list.image_cid', 0]}
                }),
                LookupStage(SubjectOption, let={'cid': '$cid'},
                            pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                      SortStage([('code', ASC)])], as_list_name='option_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'image_list')
            ]).to_list(10)

            question_list = []
            for sbj in wrong_subjects:
                picture_url = ''
                if sbj.image_list:
                    picture_url = '%s://%s%s%s%s' % (
                        SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', sbj.image_list[0].title)

                correct, error = get_cached_subject_accuracy(sbj.cid)
                all_amount = correct + error

                difficult = await SubjectDimension.get_by_cid(
                    getattr(sbj.dimension_dict, "8187881ABEAD2CF4A4F24C0AA02B2C2D"))
                category = await SubjectDimension.get_by_cid(
                    getattr(sbj.dimension_dict, "18114DC7C31B17AE35841CAE833161A2"))

                question = {'id': sbj.cid,
                            'title': sbj.title,
                            'picture_url': picture_url,
                            'category': getattr(category, 'title', ''),
                            'difficulty_degree': "%s/5" % getattr(difficult, 'ordered', 1),  # ordered: 难度
                            'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(sbj.knowledge_first, ''),
                            'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(sbj.knowledge_second, ''),
                            'resolving': sbj.resolving,
                            'correct_percent': format(float(correct) / float(all_amount),
                                                      '.2%') if all_amount else '0%',
                            'option_id': sbj.option_cid,
                            'option_list': [{
                                'id': opt.cid, 'title': opt.title, 'true_answer': opt.correct
                            } for opt in sbj.option_list]}

                question_list.append(question)

            wrong_stat = await SubjectWrongViewedStatistics.find_one({'member_cid': member.cid})
            if not wrong_stat:
                wrong_stat = SubjectWrongViewedStatistics(member_cid=member.cid, count=0)

            wrong_stat.sex = member.sex
            wrong_stat.age_group = member.age_group
            wrong_stat.education = member.education
            wrong_stat.province_code = member.province_code
            wrong_stat.city_code = member.city_code

            wrong_stat.count += 1
            await wrong_stat.save()

            r_dict = {'code': 1000, 'question_list': question_list}
        except Exception:
            logger.error(traceback.format_exc())

        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/applet/wrong/questions/get/', AppletWrongQuestionsGetHandler,
        name='wechat_applet_wrong_questions_get')
]
