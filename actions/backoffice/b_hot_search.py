# !/usr/bin/python
# -*- coding:utf-8 -*-

import collections
import copy
import traceback
import os
from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from commons.common_utils import md5, get_random_str, get_increase_code
from commons.page_utils import Paging
from db import HOT_SEARCH_STATUS_ACTIVE,HOT_SEARCH_STATUS_INACTIVE
from db.model_utils import get_administrative_division
from enums import PERMISSION_TYPE_USER_MANAGEMENT, ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT, \
    PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT, KEY_INCREASE_USER, REVIEW_REPORT_PERMS_LIST
from db.models import User, Role, AdministrativeDivision, Films,HotSearch
from logger import log_utils
from web import BaseHandler, decorators
from services import obs_service

logger = log_utils.get_logging()


class HotSearchListViewHandler(BaseHandler):
    """
    热门搜索列表
    """

    @decorators.render_template('backoffice/hot_search/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        search_name = self.get_argument('search_name', '')

        query_param = {}
        if search_name:
            query_param={'name': {'$regex': search_name}}


        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_name=%s' % \
                   (self.reverse_url("backoffice_hot_search_list"), per_page_quantity, search_name)
        paging = Paging(page_url, HotSearch, current_page=to_page_num, items_per_page=per_page_quantity, **query_param)
        await paging.pager()

        return locals()


class HotSearchEditViewHandler(BaseHandler):
    """
    编辑热门搜索
    """

    @decorators.render_template('backoffice/hot_search/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self, film_id):
        film = await Films.get_by_id(film_id)

        return {'film': film}

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self, film_id):
        res = {'code': 0}
        film = await Films.get_by_id(film_id)
        banner_files = self.request.files['banner_pic']
        if banner_files:
            banner_file = banner_files[0]
            banner_file_name = banner_file.filename
            print(datetime.now())
            # resp = obs_service.upload_file_to_obs(banner_file, banner_file_name)
            local_path, f_name = obs_service.upload_file_to_local(banner_file, banner_file_name)
            print(datetime.now())
            print(local_path, f_name)
            resp = obs_service.upload_file_to_obs(local_path, f_name)
            # film.banner_pic = resp
            # await film.save()
            # res['code']=1
            # 上传成功
            if resp.status < 300:
                film.banner_pic = resp.body.objectUrl
                if film.al_name == '':
                    film.al_name = []
                await film.save()
                res['code'] = 1
            else:
                # 上传失败
                res['code'] = -1

            if os.path.exists(local_path):
                os.remove(local_path)
        else:
            res['code'] = -2
        return res


class HotSearchStatusEditViewHandler(BaseHandler):
    """
    修改热门搜索状态
    """

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        film_ids = self.get_arguments('manager_ids[]')
        target_status = self.get_argument('target_status')

        if film_ids and target_status:
            try:
                update_requests = []
                for film_id in film_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(film_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                if update_requests:
                    modified_count = await Films.update_many(update_requests)
                    res['code'] = 1
                    res['modified_count'] = modified_count
            except Exception:
                logger.error(traceback.format_exc())
        return res





class UserDeleteViewHandler(BaseHandler):
    """
    删除用户
    """

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        user_ids = self.get_arguments('manager_ids[]')
        if user_ids:
            try:
                await User.delete_by_ids(user_ids)
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())

        return res

class HotSearchAddViewHandler(BaseHandler):

    @decorators.render_template('backoffice/hot_search/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            name = self.get_argument('name')
            hot_num = self.get_argument('hot_num')
            status = self.get_argument('status')
            if name and hot_num:
                r_count = await HotSearch.count(dict(name=name))
                if r_count > 0:
                    r_dict['code'] = -3
                else:
                    if status == 'on':
                        status = HOT_SEARCH_STATUS_ACTIVE
                    else:
                        status = HOT_SEARCH_STATUS_INACTIVE

                    hot_search = HotSearch(name=name, hot_num=int(hot_num), status=status)
                    hot_search.created_id = self.current_user.oid
                    hot_search.updated_id = self.current_user.oid
                    await hot_search.save()
                    r_dict['code'] = 1
            else:
                if not name:
                    r_dict['code'] = -1
                elif not hot_num:
                    r_dict['code'] = -2
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict

class HotSearchDeleteViewHandler(BaseHandler):

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict

URL_MAPPING_LIST = [
    url(r'/backoffice/hot_search/list/', HotSearchListViewHandler, name='backoffice_hot_search_list'),
    url(r'/backoffice/hot_search/add/', HotSearchAddViewHandler, name='backoffice_hot_search_add'),
    url(r'/backoffice/hot_search/edit/([0-9a-zA-Z_]+)/', HotSearchEditViewHandler, name='backoffice_hot_search_edit'),
    url(r'/backoffice/hot_search/status/', HotSearchStatusEditViewHandler, name='backoffice_hot_search_status'),
    url(r'/backoffice/hot_search/delete/', HotSearchDeleteViewHandler, name='backoffice_hot_search_delete'),

]
