# !/usr/bin/python
# -*- coding:utf-8 -*-


import datetime
import traceback

from commons.common_utils import datetime2str
from db import STATUS_USER_ACTIVE, STATUS_PULL_ACTION_PUSHED_SUCCESS, STATUS_PULL_ACTION_PUSHED_FAIL, \
    STATUS_PULL_ACTION_PUSHED, STATUS_PULL_ACTION_WAIT_PUSH, PUSH_CATEGORY_NOW, PUSH_RECEIVE_WECHAT, PUSH_CATEGORY_DELAY
from db.models import Questionnaire, Member, SurveyActivity, SurveyPushAction
from logger import log_utils
from tasks import app
from wechat.wechat_utils import push_active_template_message

logger = log_utils.get_logging('task_action_wechat_message')

MSG_TEMPLATE_ID = '_ASB1CRcfTM0Mi8v81LQAUqirEiW2dviSs6kYmgcTrI'

# 定时任务-延迟推送
app.register_schedule('delay_push_action_msg',
                      'tasks.instances.task_action_wechat_message.task_wechat_delay_message_push',
                      datetime.timedelta(seconds=120))


@app.task(bind=True)
def push_instant_action_message(self, survey_action_cid, status=STATUS_PULL_ACTION_WAIT_PUSH,
                                category=PUSH_CATEGORY_NOW):
    if survey_action_cid:
        survey_action = SurveyPushAction.sync_find_one({
            'cid': survey_action_cid,
            'status': status,
            'category': category,
            'pull_types': {'$in': [PUSH_RECEIVE_WECHAT]}
        })
        if survey_action:
            do_push_action_template_msg(survey_action)
    logger.info('[%s] PUSH ACTION [INSTANT] WECHAT MESSAGE END, ACTION_ID=%s.' % (self.request.id, survey_action_cid))


@app.task(bind=True)
def task_wechat_delay_message_push(self):
    survey_action_list = SurveyPushAction.sync_find({
        'status': STATUS_PULL_ACTION_WAIT_PUSH,
        'category': PUSH_CATEGORY_DELAY,
        'pull_types': {'$in': [PUSH_RECEIVE_WECHAT]},
        'push_datetime': {'lte': datetime.datetime.now()}
    })
    action_id_list = []
    if survey_action_list:
        for survey_action in survey_action_list:
            do_push_action_template_msg(survey_action)
            action_id_list.append(survey_action.oid)
    logger.info('[%s] PUSH ACTION [DELAY] WECHAT MESSAGE END, ACTION_ID=%s.' % (self.request.id, action_id_list))


def do_push_action_template_msg(survey_action):
    if survey_action:
        pushed_open_id_list = []
        pushed_list = survey_action.pushed_member_cid_list
        all_member_cid_list = survey_action.all_member_cid_list
        if pushed_list is None:
            pushed_list = []
        if all_member_cid_list is None:
            all_member_cid_list = []
        questionnaire = Questionnaire.sync_find_one({'code': survey_action.q_cid})
        if questionnaire:
            title = survey_action.title
            content = survey_action.content if survey_action.content is not None else ''
            start_date = '-'
            end_date = '-'
            surplus_times = '-'
            try:
                start_date = datetime2str(survey_action.get('start_datetime'), date_format='%Y-%m-%d')
                end_date = datetime2str(survey_action.get('end_datetime'), date_format='%Y-%m-%d')

                start_datetime = survey_action.start_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                end_datetime = survey_action.end_datetime.replace(hour=23, minute=59, second=59, microsecond=999999)
                days = (end_datetime - start_datetime).days
                seconds = (end_datetime - start_datetime).seconds
                if seconds > 0:
                    hours = int(seconds / (60 * 60))
                    seconds = seconds % (60 * 60)
                    minutes = int(seconds / 60)
                    seconds = seconds % 60
                    if seconds > 0:
                        surplus_times = u'%s 秒' % seconds
                    if minutes > 0:
                        surplus_times = u'%s 分' % minutes + surplus_times
                    if hours > 0:
                        surplus_times = u'%s 小时' % hours + surplus_times
                    if days > 0:
                        surplus_times = u'%s 天' % days + surplus_times
                else:
                    surplus_times = u'0 秒'
            except Exception:
                logger.error(traceback.format_exc())
            vehicle_code = survey_action.vehicle_code
            if vehicle_code:
                member_list = Member.sync_find({'vehicle_code': vehicle_code, 'status': STATUS_USER_ACTIVE})
                for member in member_list:
                    if member and member.cid not in pushed_list and member.cid in all_member_cid_list:
                        open_id = member.open_id
                        if open_id:
                            name = member.name
                            msg_content = get_template_msg_content(title, content, name, start_date, end_date,
                                                                   surplus_times)
                            result = push_active_template_message(MSG_TEMPLATE_ID, open_id, msg_content,
                                                                  to_url=questionnaire.get('url'))
                            if result.get('errcode') == 0:
                                pushed_open_id_list.append(open_id)
        if pushed_open_id_list:
            code_list = Member.sync_distinct('code', {'open_id': {'$in': pushed_open_id_list}})
            pushed_list.extend(code_list)
            if not survey_action.push_datetime:
                survey_action.push_datetime = datetime.datetime.now()
            survey_action.pushed_member_cid_list = pushed_list
            # 判断推送成功和推送失败
            if len(pushed_list) == len(all_member_cid_list):
                survey_action.status = STATUS_PULL_ACTION_PUSHED_SUCCESS
            elif len(pushed_list) < len(all_member_cid_list):
                survey_action.status = STATUS_PULL_ACTION_PUSHED_FAIL
            else:
                survey_action.status = STATUS_PULL_ACTION_PUSHED
            survey_action.updated_dt = datetime.datetime.now()
            survey_action.sync_save()

            # 更新活动SurveyActivity中的推送数量
            survey_activity = SurveyActivity.sync_find_one({'cid': survey_action.activity_cid})
            if survey_activity:
                pushed_amount = survey_activity.pushed_amount
                if pushed_amount is None:
                    pushed_amount = 0
                survey_activity.pushed_amount = pushed_amount + len(pushed_list)
                survey_activity.updated_dt = datetime.datetime.now()
                survey_activity.sync_save()
        else:
            if not survey_action.push_datetime:
                survey_action.push_datetime = datetime.datetime.now()
            survey_action.pushed_member_cid_list = []
            survey_action.status = STATUS_PULL_ACTION_PUSHED_FAIL
            survey_action.updated_dt = datetime.datetime.now()
            survey_action.sync_save()


def get_template_msg_content(title, content, name, start_date, end_date, surplus_times='-'):
    return {
        'first': {'value': u'尊敬的%s先生：\n\n感谢你使用我们服务！\n' % name},
        'keyword1': {'value': title},
        'keyword2': {'value': start_date},
        'keyword3': {'value': end_date},
        'keyword4': {'value': surplus_times},
        'remark': {'value': u'\n%s\n点击开始！' % content, 'color': '#0000FF'}
    }
