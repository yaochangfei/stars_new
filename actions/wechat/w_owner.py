# !/usr/bin/python
# -*- coding:utf-8 -*-
import json

from datetime import datetime

from tornado.httpclient import AsyncHTTPClient
from tornado.web import url

from commons import sms_utils
from db import STATUS_USER_ACTIVE, SOURCE_MEMBER_INTEGRAL_NOVICE, SOURCE_MEMBER_INTEGRAL_PII, \
    SOURCE_MEMBER_INTEGRAL_FIRST_SURVEY, SOURCE_MEMBER_INTEGRAL_EVERY_SURVEY
from db.model_utils import do_integral_reward
from db.models import Member, SurveyPushAction, SurveyActivity, MemberSurveyHistory
from logger import log_utils
from settings import APP_ID, SERVER_PROTOCOL, SERVER_HOST, APP_SECRET
from web import WechatBaseHandler, NonXsrfBaseHandler, decorators
from wechat import API_CODE_URL, API_USER_ACCESS_TOKEN_URL, API_USER_INFO_GET_URL

logger = log_utils.get_logging()


class WechatAuthViewHandler(WechatBaseHandler):

    async def get(self):
        code_param_dict = {
            'APPID': APP_ID,
            'REDIRECT_URI': '%s://%s%s' % (SERVER_PROTOCOL, SERVER_HOST,
                                           self.reverse_url('wechat_auto_owner_auth_token')),
            'SCOPE': 'snsapi_userinfo',
            'STATE': 'test',
        }
        code_url = API_CODE_URL.format(**code_param_dict)
        self.redirect(code_url)


class WechatAuthTokenViewHandler(NonXsrfBaseHandler):

    async def get(self):
        res = dict(domain=SERVER_HOST)
        code = self.get_argument('code')
        token_param_dict = {
            'APPID': APP_ID,
            'SECRET': APP_SECRET,
            'CODE': code,
        }
        token_url = API_USER_ACCESS_TOKEN_URL.format(**token_param_dict)

        http_client = AsyncHTTPClient()
        access_token_response = await http_client.fetch(token_url)
        access_data_dict = json.loads(access_token_response.body.decode('utf-8'))

        access_token = access_data_dict.get('access_token')
        openid = access_data_dict.get('openid')

        member = await Member.find_one(dict(open_id=openid))
        if member:
            self.render('wechat/owner/auth_repeat.html')
        else:
            # 保存用户openid access_token
            user_info_param_dict = {
                'ACCESS_TOKEN': access_token,
                'OPENID': openid,
            }
            user_info_url = API_USER_INFO_GET_URL.format(**user_info_param_dict)

            http_client = AsyncHTTPClient()
            user_info_response = await http_client.fetch(user_info_url)
            user_info_data_dict = json.loads(user_info_response.body.decode('utf-8'))

            res['open_id'] = user_info_data_dict.get('openid')
            res['nickname'] = user_info_data_dict.get('nickname')
            res['avatar'] = user_info_data_dict.get('headimgurl')
            res['union_id'] = user_info_data_dict.get('unionid')

            self.render('wechat/owner/auth_view.html', **res)

    @decorators.render_json
    async def post(self):
        res = {'code': 0}

        open_id = self.get_argument('open_id')
        validate_code = self.get_argument('validate_code')
        union_id = self.get_argument('union_id')
        avatar = self.get_argument('avatar')
        nickname = self.get_argument('nickname')
        name = self.get_argument('name')
        mobile = self.get_argument('mobile')
        vin = self.get_argument('vin')

        if open_id and avatar and nickname and vin:
            member = await Member.find_one(dict(vin=vin))
            if member:
                if not member.open_id:
                    member.union_id = union_id
                    member.open_id = open_id
                    member.nick_name = nickname
                    member.avatar = avatar
                    await member.save()
                    # 新手奖励
                    await do_integral_reward(member.code, SOURCE_MEMBER_INTEGRAL_NOVICE)
                    # 完善个人信息奖励
                    await do_integral_reward(member.code, SOURCE_MEMBER_INTEGRAL_PII)
                    res['code'] = 1
                elif member.open_id and member.open_id != open_id:
                    # 根据手机号绑定
                    res['code'] = -4
            else:
                res['code'] = -3
        else:
            if open_id and validate_code and avatar and nickname and name and mobile:
                if sms_utils.check_digit_verify_code(mobile, validate_code):
                    # 匹配AutoOwner
                    # auto_owner = await AutoOwner.find_one(dict(name=name, mobile=mobile))
                    # 根据mobile查找member
                    member = await Member.find_one(dict(mobile=mobile))
                    if member:
                        if not member.open_id:
                            member.union_id = union_id
                            member.open_id = open_id
                            member.nick_name = nickname
                            member.avatar = avatar
                            await member.save()
                            # 新手奖励cd
                            await do_integral_reward(member.code, SOURCE_MEMBER_INTEGRAL_NOVICE)
                            # 完善个人信息奖励
                            await do_integral_reward(member.code, SOURCE_MEMBER_INTEGRAL_PII)
                            res['code'] = 1
                        elif member.open_id and member.open_id != open_id:
                            # 根据车架号绑定
                            res['code'] = -4
                    else:
                        res['code'] = -3
                else:
                    res['code'] = -2
            else:
                res['code'] = -1
        return res


class WechatAuthSuccessViewHandler(WechatBaseHandler):

    @decorators.render_template('wechat/owner/auth_success.html')
    async def get(self):
        return locals()


class WechatSurveyCallbackViewHandler(NonXsrfBaseHandler):

    @decorators.render_json
    async def post(self, code):
        r_dict = {'code': 0}
        status = self.get_argument('status')
        sid = self.get_argument('sid')
        if status and sid:
            member = await Member.find_one(dict(code=code, status=STATUS_USER_ACTIVE))
            if member:
                survey_action = await SurveyPushAction.get_by_id(sid)
                if survey_action:
                    # 更新样本回收数
                    push_sample_amount = survey_action.sample_amount
                    if push_sample_amount is None:
                        push_sample_amount = 0
                    push_sample_amount += 1
                    survey_action.sample_amount = push_sample_amount

                    await survey_action.save()

                    survey_activity = await SurveyActivity.find_one(dict(cid=survey_action.activity_cid))
                    if survey_activity:
                        sample_amount = survey_activity.sample_amount
                        if sample_amount is None:
                            sample_amount = 0
                        sample_amount += 1
                        await survey_activity.save()

                    survey_history = await MemberSurveyHistory.find_one(
                        dict(member_cid=member.cid, action_id=survey_action.oid))
                    survey_history.end_datetime = datetime.now()
                    survey_history.status = int(status)
                    survey_history.updated_dt = datetime.now()

                    await survey_history.save()

                    history_count = await MemberSurveyHistory.count(dict(member_cid=member.cid))
                    if history_count == 0:
                        # 首次答题奖励
                        do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_FIRST_SURVEY)
                    else:
                        # 每次答题奖励
                        do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_EVERY_SURVEY)
                    r_dict['code'] = 1
                else:
                    r_dict['code'] = -3  # 参数调研活动不存在或已过期
            else:
                r_dict['code'] = -2  # 会员不存在或已禁用
        else:
            r_dict['code'] = -1  # 缺少参数
        return r_dict


URL_MAPPING_LIST = [
    url(r'/wechat/auto_owner/auth_token/', WechatAuthTokenViewHandler, name='wechat_auto_owner_auth_token'),
    url(r'/wechat/auto_owner/auth/', WechatAuthViewHandler, name='wechat_auto_owner_auth'),
    url(r'/wechat/auto_owner/auth/success/', WechatAuthSuccessViewHandler, name='wechat_auto_owner_auth_success'),
    url(r'/wechat/auto_owner/survey/callback/([0-9a-zA-Z_]+)/', WechatSurveyCallbackViewHandler,
        name='wechat_auto_owner_survey_callback')
]
