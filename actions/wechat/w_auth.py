# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime

from tornado.web import url

from db import PUSH_RECEIVE_WECHAT, STATUS_USER_ACTIVE, STATUS_MEMBER_SURVEY_NORMAL, STATUS_MEMBER_SURVEY_FILTERED, \
    STATUS_MEMBER_SURVEY_QUOTA_FULLED, STATUS_MEMBER_SURVEY_STARTED
from db.models import Questionnaire, SurveyPushAction, Member, MemberSurveyHistory
from motorengine import DESC
from motorengine.stages import MatchStage, LookupStage, SortStage
from motorengine.stages.limit_stage import LimitStage
from settings import APP_ID, SERVER_HOST
from web import decorators, WechatBaseHandler, KEY_MEMBER_CODE
from wechat import API_OAUTH_CODE_GET_URL, TYPE_WECHAT_OPERATE_SURVEY_HISTORY_GET, TYPE_WECHAT_OPERATE_INTEGRAL_CENTRE, \
    TYPE_WECHAT_OPERATE_TO_SURVEY, wechat_utils


class WechatOperationAuthViewHandler(WechatBaseHandler):

    @decorators.render_template('wechat/loading.html')
    async def get(self):
        op_type = self.get_argument('op_type')
        op_state = self.get_argument('op_state')
        if self.current_user:
            open_id = self.current_user.open_id
            redirect_url = await get_redirect_url(open_id, op_type, op_state)
            self.redirect(redirect_url)
            return
        auth_url = API_OAUTH_CODE_GET_URL % (APP_ID, self.get_callback_url(), '%s|%s' % (op_type, op_state))
        return locals()

    def get_callback_url(self):
        return '%s://%s/wechat/oauth20/code/' % (self.request.protocol, SERVER_HOST)


class WechatOAuth20ViewHandler(WechatBaseHandler):

    async def get(self):
        code = self.get_argument('code', None)
        state = self.get_argument('state', None)
        op_type = None
        op_state = None
        if state:
            state_list = state.split('|')
            if state_list:
                op_type = state_list[0]
                if len(state_list) > 1:
                    op_state = state_list[1]
        open_id = await wechat_utils.get_oauth20_openid(code)
        if not open_id:
            self.redirect('%s?message=%s' % (self.reverse_url('wechat_operate_message'), '错误！'))
            return
        member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
        if member:
            self.session.put(KEY_MEMBER_CODE, member).save()
            self.redirect(await get_redirect_url(open_id, op_type, op_state))
        else:
            self.redirect('%s?message=%s' % (self.reverse_url('wechat_operate_message'),
                                             '您还未认证车主信息，请至“我是车主”一栏进行车主认证！'))


class WechatOperationMsgViewHandler(WechatBaseHandler):

    @decorators.render_template('wechat/message.html')
    async def get(self):
        message = self.get_argument('message', '错误！')
        return locals()


async def get_redirect_url(open_id, op_type, op_state):
    if op_type:
        if int(op_type) == TYPE_WECHAT_OPERATE_SURVEY_HISTORY_GET:
            return '/wechat/survey/history/'
        elif int(op_type) == TYPE_WECHAT_OPERATE_INTEGRAL_CENTRE:
            return '/wechat/integral/center/'
        elif int(op_type) == TYPE_WECHAT_OPERATE_TO_SURVEY:
            if op_state:
                return await _get_survey_url(open_id, op_state)
    return '/wechat/operation/message/?message=%s' % '错误！'


async def _get_survey_url(open_id, survey_action_cid):
    if open_id and survey_action_cid:
        current_datetime = datetime.datetime.now()
        match = MatchStage({
            '$and': [
                {'cid': survey_action_cid},
                {'push_datetime': {'$lte': current_datetime}},
                {'pull_types': {'$in': [PUSH_RECEIVE_WECHAT]}},
                {'$or': [{'start_datetime': None}, {'start_datetime': {'$lte': current_datetime}}]},
                {'$or': [{'end_datetime': None}, {'end_datetime': {'$gte': current_datetime}}]}
            ]
        })
        lookup = LookupStage(Questionnaire, 'q_cid', 'cid', 'q_docs')
        sort = SortStage([('push_datetime', DESC)])
        limit = LimitStage(1)
        survey_action_list = await SurveyPushAction.aggregate([match, lookup, sort, limit]).to_list(1)
        if survey_action_list:
            survey_action = survey_action_list[0]
            if survey_action:
                q_doc_list = survey_action.q_docs
                if q_doc_list:
                    questionnaire = q_doc_list[0]
                    if questionnaire:
                        member = await Member.find_one(dict(open_id=open_id, status=STATUS_USER_ACTIVE))
                        if member:
                            history_status_list = [
                                STATUS_MEMBER_SURVEY_NORMAL,
                                STATUS_MEMBER_SURVEY_FILTERED,
                                STATUS_MEMBER_SURVEY_QUOTA_FULLED
                            ]
                            history_count = await MemberSurveyHistory.count({'member_cid': member.cid,
                                                                             'action_cid': survey_action_cid,
                                                                             'status': {'$in': history_status_list}})
                            if history_count > 0:
                                return '/wechat/operation/message/?message=%s' % '抱歉，您已经参与过本次调查，您可以点击服务号"我是车主>>最新问卷"参与其他活动。'
                            else:
                                survey_history = await MemberSurveyHistory.get_or_create(dict(member_cid=member.cid,
                                                                                              action_cid=survey_action.cid))
                                survey_history.start_datetime = datetime.datetime.now()
                                survey_history.status = STATUS_MEMBER_SURVEY_STARTED
                                survey_history.needless = {
                                    'sa_title': survey_action.title,
                                    'sa_cover': survey_action.needless.get(
                                        'cover_title') if survey_action.needless else None,
                                    'q_cid': questionnaire.get('cid'),
                                    'q_title': questionnaire.get('title')
                                }
                                await survey_history.save()
                                return questionnaire.get('url') + '?code=%s&sid=%s' % (member.code, survey_action_cid)
                return '/wechat/operation/message/?message=%s' % '错误！'
        return '/wechat/operation/message/?message=%s' % '亲，活动已结束啦，欢迎下次再来！'


URL_MAPPING_LIST = [
    url(r'/wechat/operation/message/', WechatOperationMsgViewHandler, name='wechat_operate_message'),
    url(r'/wechat/operation/auth/', WechatOperationAuthViewHandler, name='wechat_operate_auth'),
    url(r'/wechat/oauth20/code/', WechatOAuth20ViewHandler, name='wechat_oauth20_code')
]
