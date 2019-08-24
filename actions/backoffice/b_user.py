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
from db.models import User, Role, AdministrativeDivision
from logger import log_utils
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class UserListViewHandler(BaseHandler):
    """
    用户列表
    """

    @decorators.render_template('backoffice/users/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        search_name = self.get_argument('search_name', '')
        search_phone = self.get_argument('search_phone', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_phone:
            and_query_param.append({'mobile': {'$regex': search_phone}})
        if search_name:
            and_query_param.append({'$or': [{'name': {'$regex': search_name}}, {'user_name': {'$regex': search_name}}]})

        if and_query_param:
            query_param['$and'] = and_query_param

        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_name=%s&search_phone=%s' % \
                   (self.reverse_url("backoffice_user_list"), per_page_quantity, search_name, search_phone)
        paging = Paging(page_url, User, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)
        await paging.pager()

        self.do_sign_report_perm(paging.page_items)

        ad_data = await get_administrative_division()

        return locals()

    def do_sign_report_perm(self, user_list):
        if user_list:
            for user in user_list:
                setattr(user, 'review_report', False)
                for perm_code in user.permission_code_list:
                    if perm_code in REVIEW_REPORT_PERMS_LIST:
                        setattr(user, 'review_report', True)


class UserAddViewHandler(BaseHandler):
    """
    新增用户
    """

    @decorators.render_template('backoffice/users/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        user_name = self.get_argument('user_name')
        name = self.get_argument('name')
        mobile = self.get_argument('mobile')
        email = self.get_argument('email')
        password = self.get_argument('password')
        repassword = self.get_argument('repassword')
        content = self.get_argument('content')
        status = int(self.get_argument('status', STATUS_USER_ACTIVE))
        city = self.get_argument("city", '')
        province = self.get_argument("province", "")
        if user_name and name and mobile and email and password and repassword:
            if password == repassword:
                # 校验用户名
                exist_count = await User.count(dict(login_name=user_name))
                if exist_count:
                    res['code'] = -2
                else:
                    user = User(name=name, login_name=user_name.lower(), login_password=md5(password), status=status)
                    user.code = get_increase_code(KEY_INCREASE_USER)
                    user.mobile = mobile
                    user.email = email
                    user.content = content
                    user.created_id = self.current_user.oid
                    user.updated_id = self.current_user.oid
                    if city:
                        user.city = city
                    if province:
                        user.province = province
                    user_id = await user.save()

                    res['code'] = 1
                    res['manager_id'] = user_id
            else:
                res['code'] = -1
        else:
            res['code'] = -3
        return res


class UserEditViewHandler(BaseHandler):
    """
    编辑用户
    """

    @decorators.render_template('backoffice/users/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    async def get(self):
        user_id = self.get_argument('manager_id')
        user = await User.get_by_id(user_id)

        return {'manager': user, 'manager_id': user_id}

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}

        user_id = self.get_argument('manager_id', '')
        user_name = self.get_argument('user_name', '')
        name = self.get_argument('name', '')
        mobile = self.get_argument('mobile', '')
        email = self.get_argument('email', '')
        city = self.get_argument("city", '')
        province = self.get_argument("province", "")
        content = self.get_argument('content', '')
        status = int(self.get_argument('status', STATUS_USER_ACTIVE))

        if user_name and name and mobile and email and user_id:
            user = await User.get_by_id(user_id)
            if user:
                # 校验用户名
                exist_count = await User.count(dict(login_name=user_name))
                if exist_count > 1:
                    res['code'] = -2
                else:
                    user.login_name = user_name
                    user.name = name
                    user.mobile = mobile
                    user.email = email
                    user.content = content
                    user.status = status
                    if city:
                        ad_city = await AdministrativeDivision.find_one({'title': {'$regex': city}, 'record_flag': 1})
                        if not ad_city:
                            res['code'] = -4
                            return res
                        user.city = city if ad_city else ''
                    elif user.city and not city:
                        user.city = ""
                    if province:
                        ad_province = await AdministrativeDivision.find_one({'title': {'$regex': province}, 'record_flag': 1})
                        if not ad_province:
                            res['code'] = -5
                            return res
                        user.province = province if ad_province else ''
                    elif user.province and not province:
                        user.province = ""
                    user.updated_dt = datetime.now()
                    user.updated_id = self.current_user.oid
                    await user.save()

                    res['code'] = 1
            else:
                res['code'] = -1
        else:
            res['code'] = -3
        return res


class UserStatusEditViewHandler(BaseHandler):
    """
    修改用户状态
    """

    @decorators.permission_required(PERMISSION_TYPE_USER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = {'code': 0}
        user_ids = self.get_arguments('manager_ids[]')
        target_status = self.get_argument('target_status')

        if user_ids and target_status:
            try:
                update_requests = []
                for user_id in user_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(user_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                if update_requests:
                    modified_count = await User.update_many(update_requests)
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
    url(r'/backoffice/user/list/', UserListViewHandler, name='backoffice_user_list'),
    url(r'/backoffice/user/add/', UserAddViewHandler, name='backoffice_user_add'),
    url(r'/backoffice/user/edit/', UserEditViewHandler, name='backoffice_user_edit'),
    url(r'/backoffice/user/status/', UserStatusEditViewHandler, name='backoffice_user_status'),
    url(r'/backoffice/user/delete/', UserDeleteViewHandler, name='backoffice_user_delete'),
    url(r'/backoffice/user/permission/', UserPermissionViewHandler, name='backoffice_user_permission'),
    url(r'/backoffice/user/account/', UserAccountHandler, name='backoffice_account'),
    url(r'/backoffice/user/region/distribute/([0-9a-zA-Z_]+)/', UserRegionDistributeViewHandler,
        name='backoffice_region_distribute')
]
