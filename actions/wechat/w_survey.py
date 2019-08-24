# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
from tornado.web import url

from db import PUSH_RECEIVE_WECHAT, STATUS_PULL_ACTION_PUSHED, STATUS_PULL_ACTION_PUSHED_SUCCESS
from db.models import Member, SurveyPushAction, Questionnaire
from logger import log_utils
from motorengine import DESC
from motorengine.stages import MatchStage, LookupStage, SortStage, SkipStage, LimitStage
from web import decorators, WechatBaseHandler


class WechatQuestionnaireHistoryViewHandler(WechatBaseHandler):
    @decorators.render_template('wechat/survey/questionnaire_history.html')
    async def get(self):
        return locals()

    @decorators.render_json
    async def post(self):
        res = dict(code=1)
        pageNum = int(self.get_argument('pageNum', 1))
        size = int(self.get_argument('size', 9))
        current_datetime = datetime.datetime.now()

        member = await Member.get_by_id(self.current_user.oid)
        vehicle_code = member.vehicle_code

        filter_dict = {
            '$and': [
                {'vehicle_code': vehicle_code},
                {'push_datetime': {'$lte': current_datetime}},
                {'pull_types': {'$in': [PUSH_RECEIVE_WECHAT]}},
                {'status': {'$in': [STATUS_PULL_ACTION_PUSHED, STATUS_PULL_ACTION_PUSHED_SUCCESS]}}
            ]
        }
        skip = (pageNum - 1) * size if (pageNum - 1) * size > 0 else 0

        push_list = await SurveyPushAction.aggregate([
            MatchStage(filter_dict),
            LookupStage(Questionnaire, local_field='q_cid', foreign_field='cid', as_list_name='questionnaire'),
            SortStage([('push_datetime', DESC)]),
            SkipStage(skip),
            LimitStage(int(size))
        ]).to_list(int(size))
        if push_list:
            html = self.render_string('wechat/survey/questionnaire_history_data_list.html', push_list=push_list)
        else:
            html = ''

        res['html'] = html
        res['current_length'] = len(push_list)
        res['totalSize'] = await SurveyPushAction.count(filtered=filter_dict)

        return res

    def check_xsrf_cookie(self):
        pass


URL_MAPPING_LIST = [
    url(r'/wechat/survey/history/', WechatQuestionnaireHistoryViewHandler, name='wechat_survey_history'),
]
