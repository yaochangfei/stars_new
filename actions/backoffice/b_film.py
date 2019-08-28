# !/usr/bin/python
# -*- coding:utf-8 -*-

import collections
import copy
import traceback
from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne
from tornado.web import url

from commons.common_utils import md5, get_random_str, get_increase_code
from commons.page_utils import Paging
from db import STATUS_USER_ACTIVE, STATUS_ROLE_ACTIVE
from db.model_utils import get_administrative_division
from enums import PERMISSION_TYPE_USER_MANAGEMENT, ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT, \
    PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT, KEY_INCREASE_USER, REVIEW_REPORT_PERMS_LIST
from db.models import User, Role, AdministrativeDivision, Films
from logger import log_utils
from web import BaseHandler, decorators
from services import obs_service

logger = log_utils.get_logging()


class FilmListViewHandler(BaseHandler):
    """
    电影列表
    """

    @decorators.render_template('backoffice/films/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        search_name = self.get_argument('search_name', '')

        query_param = {}
        and_query_param = [{'db_mark': {'$ne': ''}},
                           {'release_time': {'$ne': ''}}]

        if search_name:
            and_query_param.append({'$or': [{'name': {'$regex': search_name}},
                                            {'actor': {'$regex': search_name}},
                                            {'director': {'$regex': search_name}},
                                            {'label': {'$regex': search_name}},
                                            ]})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_name=%s' % \
                   (self.reverse_url("backoffice_film_list"), per_page_quantity, search_name)
        paging = Paging(page_url, Films, current_page=to_page_num, items_per_page=per_page_quantity, **query_param)
        await paging.pager()

        return locals()


class FilmEditViewHandler(BaseHandler):
    """
    编辑电影
    """

    @decorators.render_template('backoffice/films/edit_view.html')
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
            resp = obs_service.upload_file_to_obs(banner_file, banner_file_name)
            print(datetime.now())
            # 上传成功
            if resp.status < 300:
                film.banner_pic = resp.body.objectUrl
                await film.save()
                res['code'] = 1
            else:
                # 上传失败
                res['code'] = -1
        else:
            res['code'] = -2
        return res


class FilmStatusEditViewHandler(BaseHandler):
    """
    修改电影状态
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


class FilmBannerStatusEditViewHandler(BaseHandler):
    """
    修改电影是否banner状态
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
                                                     {'$set': {'banner_status': int(target_status),
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


class UserPermissionViewHandler(BaseHandler):
    """
    用户权限
    """

    @decorators.render_template('backoffice/users/permission_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        user_id = self.get_argument('manager_id')
        user = await User.get_by_id(user_id)

        # 角色
        roles = await Role.find(dict(status=STATUS_ROLE_ACTIVE)).to_list(None)
        role_list = []
        c = 0
        while c < len(roles):
            role_list.append(roles[c: c + 2])
            c += 2

        # 权限
        all_permission_dict = collections.OrderedDict()
        sort_perm_list = sorted(ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT.keys())
        for code in sort_perm_list:
            i = 0
            sub_permission_list = []
            permissions = ALL_BACKOFFICE_ASSIGNABLE_PERMISSION_TYPE_DICT.get(code, [])
            while i < len(permissions):
                sub_permission_list.append(permissions[i: i + 3])
                i += 3
            all_permission_dict[code] = sub_permission_list

        return {'manager': user, 'role_list': role_list, 'all_permission_dict': all_permission_dict}

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def post(self):
        res = {'code': 0}

        user_id = self.get_argument('manager_id', '')
        user = await User.get_by_id(user_id)
        origin_role_code_list = copy.deepcopy(user.role_code_list) or []
        role_code_list = self.get_arguments('role_code_list[]')
        perm_code_list = self.get_arguments('perm_code_list[]')

        user.permission_code_list = perm_code_list
        user.role_code_list = role_code_list
        # 接入权限
        roles = await Role.find(
            dict(permission_code_list={'$in': [PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT]},
                 code={'$in': role_code_list})).to_list(None)

        if roles or PERMISSION_TYPE_SYSTEM_DOCKING_MANAGEMENT in perm_code_list:
            if not user.access_secret_id or not user.access_secret_key:
                user.access_secret_id = get_random_str(32)
                user.access_secret_key = get_random_str(64)
        else:
            user.access_secret_id = None
            user.access_secret_key = None

        try:
            user.updated_id = self.current_user.oid
            user.updated_dt = datetime.now()
            await user.save()
            # 更新角色用户数量needless
            # 新增
            new_role_code_list = list(set(role_code_list).difference(set(origin_role_code_list)))
            # 删除
            remove_role_code_list = list(set(origin_role_code_list).difference(set(role_code_list)))

            for role_code in new_role_code_list:
                role = await Role.find_one(dict(code=role_code))
                if not role.needless:
                    role.needless = {'user_amount': 1}
                else:
                    role.needless['user_amount'] = role.needless.get('user_amount', 0) + 1
                role.updated_id = self.current_user.oid
                role.updated_dt = datetime.now()
                await role.save()
            for role_code in remove_role_code_list:
                role = await Role.find_one(dict(code=role_code))
                if role.needless:
                    role.needless['user_amount'] = role.needless.get('user_amount', 1) - 1
                role.updated_id = self.current_user.oid
                role.updated_dt = datetime.now()
                await role.save()
            res['code'] = 1
        except Exception:
            logger.error(traceback.format_exc())
        return res


class UserAccountHandler(BaseHandler):
    @decorators.authenticated
    @decorators.render_template('backoffice/users/account_view.html')
    async def get(self):
        edit_account = await User.get_by_id(self.current_user.oid)
        return locals()

    @decorators.authenticated
    @decorators.render_json
    async def post(self):
        res = {'code': 0}

        account_id = self.get_argument('account_id', '')
        origin_pwd = self.get_argument('origin_pwd', '')
        new_pwd = self.get_argument('new_pwd', '')
        new_pwd_confirm = self.get_argument('new_pwd_confirm', '')
        # avatar = self.request.files['avatar']  # 头像暂时空

        if account_id and new_pwd and origin_pwd and new_pwd_confirm:
            if new_pwd_confirm != new_pwd:
                res['code'] = -2
            else:
                account = await User.get_by_id(account_id)
                if not account or account.get('password') != md5(origin_pwd):
                    res['code'] = -3
                elif account.get('password') == md5(new_pwd):
                    res['code'] = -4
                else:
                    account.login_password = md5(new_pwd)
                    account.updated_dt = datetime.now()
                    account.updated_id = self.current_user.oid
                    await account.save()
                    res['code'] = 1
        else:
            res['code'] = -1

        return res


class UserRegionDistributeViewHandler(BaseHandler):

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self, user_id):
        res = {'code': 0}
        user = await User.get_by_id(user_id)
        if user:
            data = []
            ad_cursor = AdministrativeDivision.find({'code': {'$in': user.manage_region_code_list}})
            while await ad_cursor.fetch_next:
                ad = ad_cursor.next_object()
                if ad:
                    if ad.level == 'P':
                        data.append('[p]%s' % ad.code)
                    elif ad.level == 'C':
                        data.append('[c]%s' % ad.code)
                    elif ad.level == 'D':
                        data.append('[d]%s' % ad.code)
            res['data'] = data
            res['code'] = 1
        else:
            res['code'] = -1

        return res

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def post(self, user_id):
        res = {'code': 0}

        user = await User.get_by_id(user_id)
        if user:
            region_list = self.get_arguments('region_list[]')
            result_region_list = []
            for region in region_list:
                if region:
                    region = region.replace('[c]', '').replace('[p]', '')
                    result_region_list.append(region)
            result_region_list = list(set(result_region_list))

            user.manage_region_code_list = result_region_list
            await user.save()
            res['code'] = 1
        else:
            res['code'] = -1

        return res


URL_MAPPING_LIST = [
    url(r'/backoffice/film/list/', FilmListViewHandler, name='backoffice_film_list'),
    # url(r'/backoffice/user/add/', UserAddViewHandler, name='backoffice_user_add'),
    url(r'/backoffice/film/edit/([0-9a-zA-Z_]+)/', FilmEditViewHandler, name='backoffice_film_edit'),
    url(r'/backoffice/film/status/', FilmStatusEditViewHandler, name='backoffice_film_status'),
    url(r'/backoffice/film/banner_status/', FilmBannerStatusEditViewHandler, name='backoffice_film_banner_status'),
    # url(r'/backoffice/user/delete/', UserDeleteViewHandler, name='backoffice_user_delete'),
    # url(r'/backoffice/user/permission/', UserPermissionViewHandler, name='backoffice_user_permission'),
    # url(r'/backoffice/user/account/', UserAccountHandler, name='backoffice_account'),
    # url(r'/backoffice/user/region/distribute/([0-9a-zA-Z_]+)/', UserRegionDistributeViewHandler,
    #     name='backoffice_region_distribute')
]
