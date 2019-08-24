# !/usr/bin/python
# -*- coding:utf-8 -*-
import os
import traceback
from xml.etree.ElementTree import ParseError

import datetime

from pymongo import DESCENDING, ASCENDING
from tornado.web import url

from caches.redis_utils import RedisCache
from commons.common_utils import xml2dict
from commons.upload_utils import get_upload_file_by_cid

from db.models import Member, SurveyPushAction, MemberIntegralDetail
from wechat.wechat_utils import do_integral_reward
from db import STATUS_USER_ACTIVE, PUSH_RECEIVE_WECHAT, SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY, \
    SOURCE_MEMBER_INTEGRAL_USER_RETURN
from enums import KEY_OLD_MEMBER_CACHE
from logger import log_utils
from settings import SITE_ROOT, SERVER_HOST, SERVER_PROTOCOL
from web.base import NonXsrfBaseHandler
from wechat import wechat_utils
from wechat.enums import TYPE_WECHAT_OPERATE_TO_SURVEY, EVENT_WECHAT_LATEST_SURVEY, EVENT_WECHAT_SIGN_IN, \
    EVENT_WECHAT_SUBSCRIBE
from wechat.wechat_utils import get_event_type, get_a_passive_pt_message, get_a_passive_txt_message

logger = log_utils.get_logging()


class WechatViewHandler(NonXsrfBaseHandler):
    async def get(self):
        valid_status, echostr = wechat_utils.check_signature(self)
        if valid_status:
            self.write(echostr)
        else:
            self.write('Failed')

    async def post(self):
        msg = ''
        if wechat_utils.check_signature(self)[0]:
            try:
                request_data = xml2dict(self.request.body)
                open_id = wechat_utils.get_open_id(request_data)
                service_id = wechat_utils.get_service_id(request_data)
                event_type = get_event_type(request_data)
                if event_type == EVENT_WECHAT_SUBSCRIBE:
                    msg = await self.push_improve_vehicle_owner_info_msg(open_id, service_id)
                elif event_type == EVENT_WECHAT_LATEST_SURVEY:
                    msg = await self.push_latest_questionnaire_msg(open_id, service_id)
                elif event_type == EVENT_WECHAT_SIGN_IN:
                    msg = await self.push_sign_in_msg(open_id, service_id)
            except ParseError:
                logger.error(traceback.format_exc())
        self.write(msg)
        self.finish()

    async def push_improve_vehicle_owner_info_msg(self, open_id, service_id):
        msg_xml = ''
        if open_id:
            member = await Member.find_one(filtered={'open_id': open_id})
            if not member:
                cover_url = '%s://%s%s' % (SERVER_PROTOCOL, SERVER_HOST, '/static/images/default/owner_auth.jpg')
                to_url = '%s://%s%s' % (SERVER_PROTOCOL, SERVER_HOST, '/wechat/auto_owner/auth/')
                if to_url:
                    article_dict = {
                        'title': u'车主认证',
                        'description': u'完善车主信息，即可获取最新活动，参与汽车知识PK，赶紧行动吧！',
                        'pic_url': cover_url,
                        'url': to_url
                    }
                    msg_xml = get_a_passive_pt_message(open_id, service_id, [article_dict])
        return msg_xml

    async def push_latest_questionnaire_msg(self, open_id, service_id):
        msg_xml = get_a_passive_txt_message(open_id, service_id, u'抱歉，暂时没有符合条件的活动！')
        if open_id:
            member = await Member.find_one(filtered={'open_id': open_id, 'status': STATUS_USER_ACTIVE})
            if member:
                vehicle_code = member.vehicle_code
                if vehicle_code:
                    current_datetime = datetime.datetime.now()
                    query_params = {
                        '$and': [
                            {'vehicle_code': vehicle_code},
                            {'push_datetime': {'$lte': current_datetime}},
                            {'pull_types': {'$in': [PUSH_RECEIVE_WECHAT]}},
                            {'$or': [{'start_datetime': None}, {'start_datetime': {'$lte': current_datetime}}]},
                            {'$or': [{'end_datetime': None}, {'end_datetime': {'$gte': current_datetime}}]}
                        ]
                    }
                    survey_action_list = await SurveyPushAction.find(query_params).sort(
                        [('push_datetime', DESCENDING)]).limit(1).to_list(length=1)
                    if survey_action_list:
                        survey_action = survey_action_list[0]
                        if survey_action:
                            file_cover = survey_action.cover
                            if file_cover:
                                upload_file = await get_upload_file_by_cid(file_cover)
                                pic_url = ''
                                if upload_file and upload_file.title:
                                    pic_url = '%s://%s%s' % (SERVER_PROTOCOL, SERVER_HOST,
                                                             self.static_url('files/%s' % upload_file.title))
                                if pic_url:
                                    article_dict = {
                                        'title': survey_action.title,
                                        'description': survey_action.content,
                                        'pic_url': pic_url,
                                        'url': '%s://%s/wechat/operation/auth/?op_type=%s&op_state=%s'
                                               % (SERVER_PROTOCOL, SERVER_HOST, TYPE_WECHAT_OPERATE_TO_SURVEY,
                                                  str(survey_action.oid))
                                    }
                                    msg_xml = get_a_passive_pt_message(open_id, service_id, [article_dict])
        return msg_xml

    async def push_sign_in_msg(self, open_id, service_id):
        msg_xml = ''
        member = await Member.find_one(filtered={'open_id': open_id, 'status': STATUS_USER_ACTIVE})
        if member:
            now = datetime.datetime.now()
            old_member = RedisCache.hmget(KEY_OLD_MEMBER_CACHE, (member.cid,))[0]
            if not old_member:
                integral_detail_list = await MemberIntegralDetail.find({"member_cid": member.cid}).sort(
                    [('reward_datetime', ASCENDING)]).to_list(1)
                if integral_detail_list:
                    integral_detail = integral_detail_list[0]
                    if integral_detail.reward_datetime < now + datetime.timedelta(days=-3):
                        RedisCache.hmset(KEY_OLD_MEMBER_CACHE, {member.cid: True})
                        old_member = True
            # 老用户回归
            if old_member:
                now = datetime.datetime.now()
                start_datetime = (now + datetime.timedelta(days=-3)).replace(hour=0, minute=0, second=0,
                                                                             microsecond=0)
                end_datetime = (start_datetime + datetime.timedelta(days=2)).replace(hour=23, minute=59, second=59,
                                                                                     microsecond=999)
                count = await MemberIntegralDetail.count(filtered={
                    '$and': [
                        {"member_cid": member.cid},
                        {"source": SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY},
                        {"reward_datetime": {'$gte': start_datetime}},
                        {"reward_datetime": {'$lte': end_datetime}}
                    ]
                })
                if count == 0:
                    status, m_integral = await do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_USER_RETURN)
                    if m_integral:
                        msg_xml = get_a_passive_txt_message(open_id, service_id,
                                                            u'签到成功，恭喜您获得【%s个】积分奖励！' % m_integral)
                    else:
                        msg_xml = get_a_passive_txt_message(open_id, service_id, u'签到失败，请重试！' % m_integral)
                    return msg_xml
            # 每日签到
            start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=999)
            count = await MemberIntegralDetail.count(filtered={
                '$and': [
                    {"member_cid": member.cid},
                    {"source": {'$in': [SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY, SOURCE_MEMBER_INTEGRAL_USER_RETURN]}},
                    {"reward_datetime": {'$gte': start_datetime}},
                    {"reward_datetime": {'$lte': end_datetime}}
                ]
            })
            if count == 0:
                status, m_integral = await do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_LOGIN_EVERYDAY)
                if m_integral:
                    msg_xml = get_a_passive_txt_message(open_id, service_id,
                                                        u'签到成功，恭喜您获得【%s个】积分奖励！' % m_integral)
                else:
                    msg_xml = get_a_passive_txt_message(open_id, service_id, u'签到失败，请重试！' % m_integral)
            else:
                msg_xml = get_a_passive_txt_message(open_id, service_id, u'每天只能签到一次，请明天再来！')
        else:
            msg_xml = get_a_passive_txt_message(open_id, service_id, u'您还没有完成认证，点击【我是车主>>车主认证】完成认证！')
        return msg_xml


class WechatSecurityFileViewHandler(NonXsrfBaseHandler):
    async def get(self):
        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=MP_verify_G0zBGgnnK4sZbZwk.txt')
        with open(os.path.join(SITE_ROOT, 'res', 'MP_verify_G0zBGgnnK4sZbZwk.txt'), 'rb') as f:
            while True:
                data = f.read()
                if not data:
                    break
                self.write(data)
        self.finish()


class MiniAPPSecurityFileViewHandler(NonXsrfBaseHandler):
    async def get(self):
        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=tIfUxbFxPI.txt')
        with open(os.path.join(SITE_ROOT, 'res', 'tIfUxbFxPI.txt'), 'rb') as f:
            while True:
                data = f.read()
                if not data:
                    break
                self.write(data)
        self.finish()


class MiniAppQRCodeSecurityFileViewHandler(NonXsrfBaseHandler):
    async def get(self):
        self.set_header('Content-Type', 'application/octet-stream')
        self.set_header('Content-Disposition', 'attachment; filename=6Wq1HMnZah.txt')
        with open(os.path.join(SITE_ROOT, 'res', '6Wq1HMnZah.txt'), 'rb') as f:
            while True:
                data = f.read()
                if not data:
                    break
                self.write(data)
        self.finish()


URL_MAPPING_LIST = [
    url(r'/wechat/', WechatViewHandler, name='wechat'),
    url(r'/MP_verify_G0zBGgnnK4sZbZwk.txt', WechatSecurityFileViewHandler, name='wechat_security_file'),
    url(r'/tIfUxbFxPI.txt', MiniAPPSecurityFileViewHandler, name='wechat_miniapp_security_file'),
    url(r'/6Wq1HMnZah.txt', MiniAppQRCodeSecurityFileViewHandler, name='wechat_miniapp_qrcode_security_file'),
    url(r'/miniapp/6Wq1HMnZah.txt', MiniAppQRCodeSecurityFileViewHandler, name='wechat_miniapp_qrcode_security_file2')
]
