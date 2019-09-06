# !/usr/bin/python
# -*- coding:utf-8 -*-
import re
import traceback
from datetime import datetime

from bson import ObjectId
from pymongo import UpdateOne, ReadPreference
from tornado.web import url

from commons.common_utils import str2datetime, get_increase_code
from commons.page_utils import Paging
from db import STATUS_VEHICLE_ACTIVE, STATUS_USER_ACTIVE, SOURCE_TYPE_MEMBER_SYSTEM
from db.models import Member, AdministrativeDivision, Vehicle, GameMemberSource,AppMember
from enums import PERMISSION_TYPE_MEMBER_MANAGEMENT, KEY_INCREASE_MEMBER_CODE
from logger import log_utils
from web import BaseHandler, decorators

logger = log_utils.get_logging()


class AppMemberListViewHandler(BaseHandler):
    """
    会员列表
    """

    @decorators.render_template('backoffice/app_members/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def get(self):
        search_account = self.get_argument('search_account', '')
        search_mobile = self.get_argument('search_mobile', '')

        query_param = {}
        and_query_param = [{'record_flag': 1}]
        if search_mobile:
            and_query_param.append({'mobile': {'$regex': search_mobile}})
        if search_account:
            and_query_param.append({'cid': {'$regex': search_account}})


        if and_query_param:
            query_param['$and'] = and_query_param

        # 分页
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s&search_account=%s&search_mobile=%s' % \
                   (self.reverse_url("backoffice_app_member_list"), per_page_quantity, search_account, search_mobile)
        paging = Paging(page_url, AppMember, current_page=to_page_num, items_per_page=per_page_quantity,
                        sort=['-updated_dt'], **query_param)
        await paging.pager()

        return locals()


class AppMemberAddViewHandler(BaseHandler):
    """
    新增会员
    """

    @decorators.render_template('backoffice/app_members/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def get(self):
        # 行政区划信息-联动
        province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)
        city_list = []
        if province_list[0] and province_list[0].code:
            city_list = await AdministrativeDivision.find(dict(parent_code=province_list[0].code)).to_list(None)
        # 车型信息
        vehicle_list = await Vehicle.find(dict(record_flag=1, status=STATUS_VEHICLE_ACTIVE)).to_list(None)

        return locals()

    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    @decorators.render_json
    async def post(self):
        res = dict(code=0)

        name = self.get_argument('name')
        sex = int(self.get_argument('sex', 1))
        email = self.get_argument('email')
        mobile = self.get_argument('mobile')
        birthday = self.get_argument('birthday')
        province_code = self.get_argument('province_code')  # 省份编码
        city_code = self.get_argument('city_code')  # 城市编码
        vehicle_code = self.get_argument('vehicle_code')  # 车型编号
        purchase_datetime = self.get_argument('purchase_datetime')  # 车辆购买时间
        content = self.get_argument('content')  # 备注
        status = int(self.get_argument('status', STATUS_USER_ACTIVE))

        if name and mobile and email:
            # 校验用户名
            if mobile:
                exist_count = await Member.count(dict(mobile=mobile))
                if exist_count:
                    res['code'] = -2
                    return res
            if email:
                email_valid = re.match(r"^\w+([-+.]\w+)*@\w+([-.]\w+)*\.\w+([-.]\w+)*$", email)
                exist_count = await Member.count(dict(email=email))
                if exist_count:
                    res['code'] = -3
                    return res
                if not email_valid:
                    res['code'] = -4
                    return res
            if mobile:
                member = Member()
                member.mobile = mobile
                member.code = get_increase_code(KEY_INCREASE_MEMBER_CODE)
                if email:
                    member.email = email
            else:
                member = Member()
                member.email = email
                member.code = get_increase_code(KEY_INCREASE_MEMBER_CODE)

            if name:
                member.name = name
            member.sex = sex
            if birthday:
                member.birthday = str2datetime(birthday, '%Y-%m-%d')

            if vehicle_code:
                vehicle = await Vehicle.find_one(dict(code=vehicle_code, record_flag=1))
                if vehicle:
                    member.needless['vehicle_title'] = vehicle.title
                    member.needless['vehicle_brand'] = vehicle.needless.get('brand')
                    member.needless['vehicle_category'] = vehicle.needless.get('category')
                    member.needless['vehicle_series'] = vehicle.needless.get('series')
                    member.needless['vehicle_config'] = vehicle.needless.get('config')
                    member.needless['vehicle_colour'] = vehicle.needless.get('colour')
                    member.needless['vehicle_displace'] = vehicle.needless.get('displace')
            else:
                for attr in ['vehicle_brand', 'vehicle_category', 'vehicle_series', 'vehicle_config',
                             'vehicle_colour', 'vehicle_displace', 'vehicle_title']:
                    try:
                        member.needless.pop(attr)
                    except KeyError:
                        pass

            member.content = content
            member.status = status

            # 冗余信息
            if province_code:
                province = await AdministrativeDivision.find_one(
                    dict(parent_code=None, code=province_code))
                if province:
                    member.needless['province'] = province.title
                    city = await AdministrativeDivision.find_one(
                        dict(parent_code=province_code, code=city_code))
                    if city:
                        member.needless['city'] = city.title

            member.province_code = province_code
            member.city_code = city_code
            member.source = SOURCE_TYPE_MEMBER_SYSTEM

            if vehicle_code:
                if vehicle_code:
                    vehicle = await Vehicle.find_one(dict(code=vehicle_code, record_flag=1))
                    if vehicle:
                        member.needless['vehicle_title'] = vehicle.title
                        member.needless['vehicle_brand'] = vehicle.needless.get('brand')
                        member.needless['vehicle_category'] = vehicle.needless.get('category')
                        member.needless['vehicle_series'] = vehicle.needless.get('series')
                        member.needless['vehicle_config'] = vehicle.needless.get('config')
                        member.needless['vehicle_colour'] = vehicle.needless.get('colour')
                        member.needless['vehicle_displace'] = vehicle.needless.get('displace')
                member.vehicle_code = vehicle_code

            if purchase_datetime:
                member.purchase_datetime = str2datetime(purchase_datetime, '%Y-%m')

            member.status = status
            member_id = await member.save()

            res['code'] = 1
            res['member_id'] = member_id
        else:
            res['code'] = -1
        return res


class AppMemberDetailViewHandler(BaseHandler):
    """
    会员详情
    """

    @decorators.render_template('backoffice/app_members/detail_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def get(self):
        member = await Member.get_by_id(self.get_argument('member_id'))
        source = await GameMemberSource.find_one({'code': str(member.source)})
        member.source = source.title
        return locals()


class AppMemberEditViewHandler(BaseHandler):
    """
    编辑会员信息
    """

    @decorators.render_template('backoffice/app_members/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def get(self):
        member_id = self.get_argument('member_id')
        member = await Member.find_one({'_id': ObjectId(member_id)}, read_preference=ReadPreference.PRIMARY)
        # 行政区划信息-联动
        province_list = await AdministrativeDivision.find(dict(parent_code=None)).to_list(None)
        city_list = []
        district_code = ''
        province_code = ''
        city_code = ''
        location_district_list = []
        location_city_list = []
        if member.province_code:
            city_list = await AdministrativeDivision.find(dict(parent_code=member.province_code), read_preference=ReadPreference.PRIMARY).to_list(None)
        if member.city_code:
            district_list = await AdministrativeDivision.find(dict(parent_code=member.city_code)).to_list(None)
        if member.auth_address.get('province'):
            province = await AdministrativeDivision.find_one(dict(parent_code=None, title=member.auth_address['province']))
            province_code = province.code
            location_city_list = await AdministrativeDivision.find(dict(parent_code=province_code),
                                                                   read_preference=ReadPreference.PRIMARY).to_list(None)
            if member.auth_address.get('city'):
                city = await AdministrativeDivision.find_one(dict(parent_code=province_code, title=member.auth_address['city']), read_preference=ReadPreference.PRIMARY)
                city_code = city.code
                if member.auth_address.get('district'):
                    location_district_list = await AdministrativeDivision.find(dict(parent_code=city_code), read_preference=ReadPreference.PRIMARY).to_list(None)
                    district = await AdministrativeDivision.find_one(dict(parent_code=city_code, title=member.auth_address['district']))
                    district_code = district.code
        # 车型信息
        vehicle_list = await Vehicle.find(dict(record_flag=1, status=STATUS_VEHICLE_ACTIVE)).to_list(None)

        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def post(self):
        res = {'code': 0}

        member_id = self.get_argument('member_id')
        member = await Member.get_by_id(member_id)
        if member:
            province_code = self.get_argument('province_code')
            city_code = self.get_argument('city_code')
            location_province_code = self.get_argument('location_province_code', '')
            location_city_code = self.get_argument('location_city_code', '')
            location_district_code = self.get_argument('location_district_code', '')
            purchase_datetime = self.get_argument('purchase_datetime')
            content = self.get_argument('content')
            status = int(self.get_argument('status', STATUS_USER_ACTIVE))
            vehicle_code = self.get_argument('vehicle_code')
            # 冗余信息
            if province_code:
                province = await AdministrativeDivision.find_one(
                    dict(parent_code=None, code=province_code))
                if province:
                    member.needless['province'] = province.title
                    city = await AdministrativeDivision.find_one(
                        dict(parent_code=province_code, code=city_code))
                    if city:
                        member.needless['city'] = city.title
            if location_province_code:
                location_province = await AdministrativeDivision.find_one(dict(parent_code=None, code=location_province_code))
                if location_province:
                    member.auth_address = {'province': location_province.title}
                    if location_city_code:
                        location_city = await AdministrativeDivision.find_one(dict(parent_code=location_province_code, code=location_city_code))
                        if location_city:
                            member.auth_address['city'] = location_city.title
                            if location_district_code:
                                location_district = await AdministrativeDivision.find_one(dict(parent_code=location_city_code, code=location_district_code))
                                if location_district:
                                    member.auth_address['district'] = location_district.title
                            else:
                                return {'code': -99}
            if vehicle_code:
                vehicle = await Vehicle.find_one(dict(code=vehicle_code, record_flag=1))
                if vehicle:
                    member.needless['vehicle_title'] = vehicle.title
                    member.needless['vehicle_brand'] = vehicle.needless.get('brand')
                    member.needless['vehicle_category'] = vehicle.needless.get('category')
                    member.needless['vehicle_series'] = vehicle.needless.get('series')
                    member.needless['vehicle_config'] = vehicle.needless.get('config')
                    member.needless['vehicle_colour'] = vehicle.needless.get('colour')
                    member.needless['vehicle_displace'] = vehicle.needless.get('displace')
            else:
                for attr in ['vehicle_brand', 'vehicle_category', 'vehicle_series', 'vehicle_config',
                             'vehicle_colour', 'vehicle_displace', 'vehicle_title']:
                    try:
                        member.needless.pop(attr)
                    except KeyError:
                        pass
            member.province_code = province_code
            member.city_code = city_code
            member.content = content
            member.status = status
            member.updated_dt = datetime.now()
            member.updated_id = self.current_user.oid
            member.vehicle_code = vehicle_code
            if purchase_datetime:
                member.purchase_datetime = datetime.strptime(purchase_datetime, '%Y-%m')

            await member.save()

            res['code'] = 1
        return res


class AppMemberStatusEditViewHandler(BaseHandler):
    """
    修改车主状态
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        member_ids = self.get_arguments('member_ids[]')
        target_status = self.get_argument('target_status')
        if member_ids and target_status:
            try:
                update_requests = []
                for member_id in member_ids:
                    update_requests.append(UpdateOne({'_id': ObjectId(member_id)},
                                                     {'$set': {'status': int(target_status),
                                                               'updated_dt': datetime.now(),
                                                               'updated_id': self.current_user.oid}}))
                modified_count = await Member.update_many(update_requests)

                res['code'] = 1
                res['modified_count'] = modified_count
            except Exception:
                logger.error(traceback.format_exc())
        return res


class AppMemberDeleteViewHandler(BaseHandler):
    """
    删除会员信息
    """

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_MEMBER_MANAGEMENT)
    async def post(self):
        res = {'code': 0}
        member_ids = self.get_arguments('member_ids[]')
        if member_ids:
            try:
                await Member.delete_by_ids(member_ids)
                res['code'] = 1
            except Exception:
                logger.error(traceback.format_exc())

        return res





URL_MAPPING_LIST = [
    url(r'/backoffice/app_member/list/', AppMemberListViewHandler, name='backoffice_app_member_list'),
    url(r'/backoffice/app_member/add/', AppMemberAddViewHandler, name='backoffice_app_member_add'),
    url(r'/backoffice/app_member/detail/', AppMemberDetailViewHandler, name='backoffice_app_member_detail'),
    url(r'/backoffice/app_member/edit/', AppMemberEditViewHandler, name='backoffice_app_member_edit'),
    url(r'/backoffice/app_member/status/', AppMemberStatusEditViewHandler, name='backoffice_app_member_status'),
    url(r'/backoffice/app_member/delete/', AppMemberDeleteViewHandler, name='backoffice_app_member_delete'),

]
