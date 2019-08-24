# !/usr/bin/python
# -*- coding:utf-8 -*-

import traceback
import uuid

from datetime import datetime

from bson import ObjectId
from tornado.web import url

from commons.common_utils import md5, get_increase_code
from commons.page_utils import Paging
from commons.upload_utils import save_upload_file, drop_disk_file_by_cid
from db import STATUS_VEHICLE_ACTIVE, PUSH_CATEGORY_NOW, PUSH_CATEGORY_DELAY, CATEGORY_UPLOAD_FILE_IMG_MSG_PUSH, \
    STATUS_PULL_ACTION_WAIT_PUSH, STATUS_PULL_ACTION_PUSHED_SUCCESS, STATUS_PULL_ACTION_PUSHED_FAIL, SEX_DICT
from db.models import Questionnaire, SurveyPushAction, Vehicle, UploadFiles, SurveyActivity, Member, \
    MemberSurveyHistory, AdministrativeDivision
from enums import PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT, KEY_INCREASE_SURVEY_ACTIVITY_CODE
from logger import log_utils
from tasks.instances.task_action_wechat_message import push_instant_action_message
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class ActivityListViewHandler(BaseHandler):
    """
    活动列表
    """

    @decorators.render_template('backoffice/activities/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        search_activity_title = self.get_argument('search_activity_title', '')
        search_questionnaire_title = self.get_argument('search_questionnaire_title', '')

        query_param = {}
        and_query_param = [{'record_flag': 1, 'code': {'$ne': None}}]
        if search_questionnaire_title:
            and_query_param.append({'title': {'$regex': search_questionnaire_title}})
        if and_query_param:
            query_param['$and'] = and_query_param

        q_cid_list = await Questionnaire.distinct('cid', filtered=query_param)
        activity_query_param = {'record_flag': 1, 'q_cid': {'$in': q_cid_list}}
        if search_activity_title:
            activity_query_param['title'] = {'$regex': search_activity_title}

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_activity_title=%s&search_questionnaire_title=%s' % \
                   (self.reverse_url("backoffice_activity_list"), per_page_quantity, search_activity_title,
                    search_questionnaire_title)
        paging = Paging(page_url, SurveyActivity, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **activity_query_param)
        await paging.pager()

        return locals()


class ActivityAddViewHandler(BaseHandler):
    """
    新增活动
    """

    @decorators.render_template('backoffice/activities/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        title = self.get_argument('title')
        content = self.get_argument('content')
        q_code = self.get_argument('q_code')
        if title and q_code:
            questionnaire = await Questionnaire.find_one({'code': q_code, 'record_flag': 1})
            if not questionnaire:
                res['code'] = -3
            else:
                try:
                    # 保存活动
                    survey_activity = SurveyActivity(code=md5(uuid.uuid1().hex), q_cid=questionnaire.cid, title=title)
                    survey_activity.content = content
                    # 问卷
                    survey_activity.needless = {'q_title': questionnaire.title}

                    activity_id = await survey_activity.save()
                    res['code'] = 1
                    res['activity_id'] = activity_id
                except Exception:
                    logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class ActivityDeleteViewHandler(BaseHandler):
    """
    删除活动
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        activity_ids = self.get_arguments('activity_ids[]')
        if activity_ids:
            try:
                # 删除所有推送？
                await SurveyActivity.delete_by_ids(activity_ids)
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())

        return res


class ActivityEditViewHandler(BaseHandler):
    """
    编辑活动
    """

    @decorators.render_template('backoffice/activities/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        activity = await SurveyActivity.get_by_id(self.get_argument('activity_id'))
        questionnaire = await Questionnaire.find_one({'cid': activity.q_cid, 'record_flag': 1})
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = dict(code=0)

        activity_id = self.get_argument('activity_id')
        title = self.get_argument('title')
        content = self.get_argument('content')
        q_code = self.get_argument('q_code')
        if activity_id and title and q_code:
            questionnaire = await Questionnaire.find_one({'code': q_code, 'record_flag': 1})
            if not questionnaire:
                res['code'] = -3
            else:
                try:
                    survey_activity = await SurveyActivity.get_by_id(activity_id)
                    survey_activity.q_cid = questionnaire.cid
                    survey_activity.title = title
                    survey_activity.content = content
                    survey_activity.needless['q_title'] = questionnaire.title

                    activity_id = await survey_activity.save()
                    res['code'] = 1
                    res['activity_id'] = activity_id
                except Exception:
                    logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class ActivityPushListViewHandler(BaseHandler):
    """
    推送中心
    """

    @decorators.render_template('backoffice/activities/push_list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        search_push_time = self.get_argument('search_push_time')
        activity_cid = self.get_argument('activity_cid')
        push_result = self.get_argument('push_result', '')

        survey_activity = await SurveyActivity.find_one({'cid': activity_cid, 'record_flag': 1})
        # 推送总人数
        push_member_amount = survey_activity.pushed_amount if survey_activity.pushed_amount else 0
        # 样本回收数
        all_sample_amount = survey_activity.sample_amount if survey_activity.sample_amount else 0
        # 样本回收率
        sample_rate = '%.2f' % (all_sample_amount * 100 / push_member_amount) if push_member_amount else 0.00
        # 推送数量
        all_push_amount = await SurveyPushAction.count(filtered={'activity_cid': activity_cid, 'record_flag': 1})
        # 推送成功数
        success_push_amount = await SurveyPushAction.count(filtered={'activity_cid': activity_cid, 'record_flag': 1,
                                                                     'status': STATUS_PULL_ACTION_PUSHED_SUCCESS})
        # 推送失败数
        fail_push_amount = await SurveyPushAction.count(filtered={'activity_cid': activity_cid, 'record_flag': 1,
                                                                  'status': STATUS_PULL_ACTION_PUSHED_FAIL})

        push_query_param = {'record_flag': 1, 'activity_cid': activity_cid}
        if push_result:
            push_query_param['status'] = int(push_result)
        if search_push_time:
            push_time = datetime.strptime(search_push_time, '%Y-%m-%d')
            push_query_param['push_datetime'] = {
                '$gte': push_time.replace(hour=0, minute=0, second=0),
                '$lte': push_time.replace(hour=23, minute=59, second=59),
            }

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_push_time=%s' % \
                   (self.reverse_url("backoffice_activity_push_list"), per_page_quantity, search_push_time)
        paging = Paging(page_url, SurveyPushAction, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **push_query_param)
        await paging.pager()

        return locals()


class ActivityPushAddViewHandler(BaseHandler):
    """
    发起推送
    """

    @decorators.render_template('backoffice/activities/push_add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        # 行政区划信息-联动
        province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)
        city_list = []
        if province_list[0] and province_list[0].code:
            city_list = await AdministrativeDivision.find(dict(parent_code=province_list[0].code)).to_list(None)
        # 车型信息
        vehicle_list = await Vehicle.find(dict(record_flag=1, status=STATUS_VEHICLE_ACTIVE)).to_list(None)
        activity_cid = self.get_argument('activity_cid')

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}

        activity_cid = self.get_argument('activity_cid')
        category = self.get_argument('category', PUSH_CATEGORY_NOW)
        push_datetime = self.get_argument('push_datetime')
        pull_types = self.get_argument('pull_types')
        start_datetime = self.get_argument('start_datetime')
        end_datetime = self.get_argument('end_datetime')
        cover_metas = self.request.files.get('cover')
        vehicle_code = self.get_argument('vehicle_code')
        province_code = self.get_argument('province_code')
        city_code = self.get_argument('city_code')
        sex = self.get_argument('sex')

        if activity_cid and category and cover_metas:
            if int(category) == PUSH_CATEGORY_DELAY and not push_datetime:
                res['code'] = -2
            else:
                survey_activity = await SurveyActivity.find_one({'cid': activity_cid, 'record_flag': 1})
                if not survey_activity:
                    res['code'] = -3
                else:
                    try:
                        # 保存文件
                        save_res = await save_upload_file(self, 'cover', category=CATEGORY_UPLOAD_FILE_IMG_MSG_PUSH)
                        if save_res:
                            push_action = SurveyPushAction(activity_cid=activity_cid, title=survey_activity.title,
                                                           q_cid=survey_activity.q_cid, category=int(category),
                                                           sample_amount=0)

                            term = dict(vehicle_code=vehicle_code)
                            if province_code:
                                term['province_code'] = province_code
                            if city_code:
                                term['city_code'] = city_code
                            if sex:
                                term['sex'] = int(sex)
                            term['open_id'] = {'$ne': None}

                            # 所有推送用户
                            push_action.all_member_cid_list = await Member.distinct('cid', term)

                            push_action.content = survey_activity.content

                            vehicle = await Vehicle.find_one(dict(code=vehicle_code))
                            needless = {'q_title': survey_activity.needless.get('q_title'),
                                        'vehicle_title': vehicle.title}
                            if province_code:
                                province = await AdministrativeDivision.find_one({'code': province_code})
                                needless["province_title"] = province.title
                            if city_code:
                                city = await AdministrativeDivision.find_one({'code': city_code})
                                needless["city_title"] = city.title
                            if sex:
                                needless["sex"] = SEX_DICT.get(int(sex))
                            # 同时冗余问卷名称
                            push_action.needless = needless
                            push_action.vehicle_code = vehicle_code
                            push_action.pull_types = list(map(int, pull_types.split(','))) if pull_types else []
                            push_action.cover = save_res[0]

                            cover = await UploadFiles.find_one(dict(cid=push_action.cover))
                            push_action.needless['cover_title'] = 'files/%s' % cover.title

                            push_action.push_datetime = datetime.strptime(push_datetime, '%Y-%m-%d %H:%M:%S') if int(
                                category) == PUSH_CATEGORY_DELAY else datetime.now()
                            push_action.status = STATUS_PULL_ACTION_WAIT_PUSH
                            if start_datetime:
                                push_action.start_datetime = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')
                            if end_datetime:
                                push_action.end_datetime = datetime.strptime(end_datetime, '%Y-%m-%d %H:%M:%S')
                            push_action.created_id = self.current_user.oid
                            push_action.updated_id = self.current_user.oid

                            await push_action.save()
                            res['code'] = 1
                            res['push_id'] = push_action.cid
                            # 立即推送消息
                            if push_action.category == PUSH_CATEGORY_NOW:
                                push_instant_action_message.delay(push_action.cid)
                    except Exception:
                        logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class ActivityPushDeleteViewHandler(BaseHandler):
    """
    删除推送
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        push_ids = self.get_arguments('push_ids[]')
        if push_ids:
            try:
                push_id_list = [ObjectId(p_id) for p_id in push_ids]
                placard_list = await SurveyPushAction.distinct('cover',
                                                               {'_id': {'$in': push_id_list}, 'cover': {'$ne': None}})
                if placard_list:
                    await drop_disk_file_by_cid(placard_list)

                    # 删除推送，更新活动的推送总人数和样本回收
                await SurveyPushAction.delete_by_ids(push_ids)
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())
        return res


class ActivityPushEditViewHandler(BaseHandler):
    """
    编辑推送
    """

    @decorators.render_template('backoffice/activities/push_edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        push_id = self.get_argument('push_id')
        activity_cid = self.get_argument('activity_cid')

        push = await SurveyPushAction.get_by_id(push_id)
        # 车型信息
        vehicle_list = await Vehicle.find(dict(record_flag=1, status=STATUS_VEHICLE_ACTIVE)).to_list(None)
        # 图片
        cover = await UploadFiles.find_one(dict(code=push.cover))

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}

        push_id = self.get_argument('push_id')
        activity_cid = self.get_argument('activity_cid')
        category = self.get_argument('category', PUSH_CATEGORY_NOW)
        push_datetime = self.get_argument('push_datetime')
        pull_types = self.get_argument('pull_types')
        start_datetime = self.get_argument('start_datetime')
        end_datetime = self.get_argument('end_datetime')
        vehicle_code = self.get_argument('vehicle_code')
        cover_metas = self.request.files.get('cover')
        cover_code = self.get_argument('cover_code')

        if vehicle_code and push_id and category and (cover_metas or cover_code):
            if int(category) == PUSH_CATEGORY_DELAY and not push_datetime:
                res['code'] = -2
            else:
                survey_activity = await SurveyActivity.find_one({'cid': activity_cid, 'record_flag': 1})
                if not survey_activity:
                    res['code'] = -3
                else:
                    try:
                        save_res = await save_upload_file(self, 'cover', category=CATEGORY_UPLOAD_FILE_IMG_MSG_PUSH,
                                                          file_cid=cover_code)
                        if save_res or cover_code:
                            push_action = await SurveyPushAction.get_by_id(push_id)
                            push_action.activity_cid = activity_cid
                            push_action.sample_amount = 0

                            # 所有推送用户
                            member_cid_list = await Member.distinct('cid', dict(vehicle_code=vehicle_code))
                            push_action.all_member_cid_list = member_cid_list

                            push_action.title = survey_activity.title
                            push_action.content = survey_activity.content
                            push_action.q_cid = survey_activity.q_cid

                            vehicle = await Vehicle.find_one(dict(code=vehicle_code))
                            # 同时冗余问卷名称
                            push_action.needless = {'q_title': survey_activity.needless.get('q_title'),
                                                    'vehicle_title': vehicle.title}
                            push_action.category = int(category)
                            push_action.vehicle_code = vehicle_code
                            push_action.pull_types = list(map(int, pull_types.split(','))) if pull_types else []

                            push_action.cover = save_res[0] if save_res else cover_code
                            cover = await UploadFiles.find_one(dict(cid=push_action.cover))

                            push_action.needless['cover_title'] = 'files/%s' % cover.title

                            push_action.push_datetime = datetime.strptime(push_datetime, '%Y-%m-%d %H:%M:%S') \
                                if category == str(PUSH_CATEGORY_DELAY) else datetime.now()
                            if start_datetime:
                                push_action.start_datetime = datetime.strptime(start_datetime, '%Y-%m-%d %H:%M:%S')
                            if end_datetime:
                                push_action.end_datetime = datetime.strptime(end_datetime, '%Y-%m-%d %H:%M:%S')

                            push_action.updated_id = self.current_user.oid
                            push_action.updated_dt = datetime.now()

                            push_id = await push_action.save()

                            res['code'] = 1
                            res['push_id'] = push_id

                            # 立即发送
                            if push_action.category == PUSH_CATEGORY_NOW:
                                push_instant_action_message.delay(push_id)
                    except Exception:
                        logger.error(traceback.format_exc())
        else:
            res['code'] = -1

        return res


class ActivityPushDetailViewHandler(BaseHandler):
    """
    推送成功详情页面
    """

    @decorators.render_template('backoffice/activities/push_detail_view.html')
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def get(self):
        search_member_code = self.get_argument('search_member_code', '')
        search_member_name = self.get_argument('search_member_name', '')
        search_survey_status = self.get_argument('search_survey_status', '')
        activity_cid = self.get_argument('activity_cid', '')
        push_cid = self.get_argument('push_cid', '')

        # 判断推送状态
        activity = await SurveyActivity.get_by_cid(activity_cid)
        push = await SurveyPushAction.get_by_cid(push_cid)

        all_member_cid_list = push.all_member_cid_list if push.all_member_cid_list else []

        # 判断答卷状态
        survey_history_query_param = {'record_flag': 1, 'action_cid': push_cid}
        member_survey_history = await MemberSurveyHistory.find(survey_history_query_param).to_list(None)
        survey_member_cid_list = await MemberSurveyHistory.distinct('member_cid', survey_history_query_param)

        member_query_param = {'record_flag': 1, 'cid': {'$in': all_member_cid_list}}
        if search_member_code:
            member_query_param['code']['$regex'] = search_member_code
        if search_member_name:
            member_query_param['name'] = {'$regex': search_member_name}
        if search_survey_status == '1':
            member_query_param.setdefault('cid', {})['$in'] = survey_member_cid_list
        if search_survey_status == '0':
            member_query_param.setdefault('cid', {})['$nin'] = survey_member_cid_list

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_member_code=%s&search_member_name=%s' \
                   '&search_survey_status=%s' % (
                       self.reverse_url("backoffice_activity_push_detail"), per_page_quantity, search_member_code,
                       search_member_name, search_survey_status)
        paging = Paging(page_url, Member, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **member_query_param)
        await paging.pager()

        return locals()


class ActivityPushRePushViewHandler(BaseHandler):
    """
    重新推送
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_QUESTIONNAIRE_ACTIVITY_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        push_id = self.get_argument('push_id')
        try:
            push = await SurveyPushAction.get_by_id(push_id)
            if push:
                push_instant_action_message.delay(push_id, STATUS_PULL_ACTION_PUSHED_FAIL, PUSH_CATEGORY_NOW)
                res['code'] = 1
            else:
                res['code'] = -1
        except Exception:
            logger.error(traceback.format_exc())

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/activity/list/', ActivityListViewHandler, name='backoffice_activity_list'),
    url(r'/backoffice/activity/add/', ActivityAddViewHandler, name='backoffice_activity_add'),
    url(r'/backoffice/activity/delete/', ActivityDeleteViewHandler, name='backoffice_activity_delete'),
    url(r'/backoffice/activity/edit/', ActivityEditViewHandler, name='backoffice_activity_edit'),
    url(r'/backoffice/activity/push/list/', ActivityPushListViewHandler, name='backoffice_activity_push_list'),
    url(r'/backoffice/activity/push/add/', ActivityPushAddViewHandler, name='backoffice_activity_push_add'),
    url(r'/backoffice/activity/push/delete/', ActivityPushDeleteViewHandler, name='backoffice_activity_push_delete'),
    url(r'/backoffice/activity/push/edit/', ActivityPushEditViewHandler, name='backoffice_activity_push_edit'),
    url(r'/backoffice/activity/push/detail/', ActivityPushDetailViewHandler, name='backoffice_activity_push_detail'),
    url(r'/backoffice/activity/push/re_push/', ActivityPushRePushViewHandler, name='backoffice_activity_push_re_push'),
]
