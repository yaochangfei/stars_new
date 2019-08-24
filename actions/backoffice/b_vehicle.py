# !/usr/bin/python
# -*- coding:utf-8 -*-
import traceback

import datetime

from bson import ObjectId
from pymongo import UpdateOne
from tornado import gen
from tornado.web import url

from commons.page_utils import Paging
from db.models import Vehicle, VehicleAttribute
from db import STATUS_VEHICLE_ACTIVE, STATUS_VEHICLE_INACTIVE
from enums import PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT
from logger import log_utils
from web import decorators
from web.base import BaseHandler

logger = log_utils.get_logging()


class VehicleListViewHandler(BaseHandler):
    @decorators.render_template('backoffice/vehicle/list_view.html')
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def get(self):
        query_params = {'record_flag': 1}
        kw_name = self.get_argument('kw_name', '')
        kw_category = self.get_argument('kw_category', '')
        if kw_name:
            query_params['title'] = {'$regex': kw_name, '$options': 'i'}
        if kw_category:
            query_params['needless.category'] = {'$regex': kw_category, '$options': 'i'}
        # 分页 START
        per_page_quantity = int(self.get_argument('per_page_quantity', 10))
        to_page_num = int(self.get_argument('page', 1))
        page_url = '%s?page=$page&per_page_quantity=%s' % (
            self.reverse_url("backoffice_vehicle_list"), per_page_quantity)
        paging = Paging(page_url, Vehicle, current_page=to_page_num,
                        items_per_page=per_page_quantity, sort=['-updated_dt'], **query_params)
        await paging.pager()
        # 分页 END

        return locals()


class VehicleAddViewHandler(BaseHandler):
    @decorators.render_template('backoffice/vehicle/add_view.html')
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def get(self):
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            code = self.get_argument('code', None)  # 车辆编码
            title = self.get_argument('title', None)  # 车辆名称
            brand = self.get_argument('brand', None)  # 车辆品牌
            category = self.get_argument('category', None)  # 车辆类别
            series = self.get_argument('series', None)  # 车辆系列
            config = self.get_argument('config', None)  # 车辆配置
            colour = self.get_argument('colour', None)  # 车辆颜色
            displace = self.get_argument('displace', None)  # 车辆排量
            status = self.get_argument('status', None)  # 状态
            if code and title and category:
                r_count = await Vehicle.count(filtered={'code': code})
                if r_count > 0:
                    r_dict['code'] = -4
                else:
                    if status == 'on':
                        status = STATUS_VEHICLE_ACTIVE
                    else:
                        status = STATUS_VEHICLE_INACTIVE
                    vehicle = Vehicle()
                    vehicle.code = code
                    vehicle.title = title
                    vehicle.brand = brand
                    vehicle.category = category
                    vehicle.series = series
                    vehicle.config = config
                    vehicle.colour = colour
                    vehicle.displace = displace
                    vehicle.status = status
                    vehicle.created_id = self.current_user.oid
                    vehicle.updated_id = self.current_user.oid

                    # 冗余信息
                    if not isinstance(vehicle.needless, dict):
                        vehicle.needless = {}
                    brand_attr = await VehicleAttribute.find_one(filtered={'code': brand})
                    category_attr = await VehicleAttribute.find_one(filtered={'code': category})
                    displace_attr = await VehicleAttribute.find_one(filtered={'code': displace})
                    series_attr = await VehicleAttribute.find_one(filtered={'code': series})
                    config_attr = await VehicleAttribute.find_one(filtered={'code': config})
                    colour_attr = await VehicleAttribute.find_one(filtered={'code': colour})
                    vehicle.needless['brand'] = brand_attr.title if brand_attr else '-'
                    vehicle.needless['category'] = category_attr.title if category_attr else '-'
                    vehicle.needless['series'] = series_attr.title if series_attr else '-'
                    vehicle.needless['config'] = config_attr.title if config_attr else '-'
                    vehicle.needless['colour'] = colour_attr.title if colour_attr else '-'
                    vehicle.needless['displace'] = displace_attr.title if displace_attr else '-'

                    await vehicle.save()
                    r_dict['code'] = 1
            else:
                if not code:
                    r_dict['code'] = -1
                elif not title:
                    r_dict['code'] = -2
                elif not category:
                    r_dict['code'] = -3
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class VehicleEditViewHandler(BaseHandler):
    @decorators.render_template('backoffice/vehicle/edit_view.html')
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def get(self, vehicle_id):
        vehicle = await Vehicle.get_by_id(vehicle_id)
        return locals()

    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def post(self, vehicle_id):
        r_dict = {'code': 0}
        try:
            vehicle = await Vehicle.get_by_id(vehicle_id)
            if vehicle:
                title = self.get_argument('title', None)  # 车辆名称
                brand = self.get_argument('brand', None)  # 车辆品牌
                category = self.get_argument('category', None)  # 车辆类别
                series = self.get_argument('series', None)  # 车辆系列
                config = self.get_argument('config', None)  # 车辆配置
                colour = self.get_argument('colour', None)  # 车辆颜色
                displace = self.get_argument('displace', None)  # 车辆排量
                status = self.get_argument('status', None)  # 状态
                if title and category:
                    if status == 'on':
                        status = STATUS_VEHICLE_ACTIVE
                    else:
                        status = STATUS_VEHICLE_INACTIVE
                    vehicle.title = title  # 车辆名称
                    vehicle.brand = brand  # 车辆品牌
                    vehicle.category = category  # 车辆类别
                    vehicle.series = series  # 车辆系列
                    vehicle.config = config  # 车辆配置
                    vehicle.colour = colour  # 车辆颜色
                    vehicle.displace = displace  # 车辆排量
                    vehicle.status = status  # 状态
                    vehicle.updated_dt = datetime.datetime.now()
                    vehicle.updated_id = self.current_user.oid

                    # 冗余信息
                    if not isinstance(vehicle.needless, dict):
                        vehicle.needless = {}
                    brand_attr = await VehicleAttribute.find_one(filtered={'code': brand})
                    category_attr = await VehicleAttribute.find_one(filtered={'code': category})
                    displace_attr = await VehicleAttribute.find_one(filtered={'code': displace})
                    series_attr = await VehicleAttribute.find_one(filtered={'code': series})
                    config_attr = await VehicleAttribute.find_one(filtered={'code': config})
                    colour_attr = await VehicleAttribute.find_one(filtered={'code': colour})
                    vehicle.needless['brand'] = brand_attr.title if brand_attr else '-'
                    vehicle.needless['category'] = category_attr.title if brand_attr else '-'
                    vehicle.needless['series'] = series_attr.title if series_attr else '-'
                    vehicle.needless['config'] = config_attr.title if config_attr else '-'
                    vehicle.needless['colour'] = colour_attr.title if colour_attr else '-'
                    vehicle.needless['displace'] = displace_attr.title if displace_attr else '-'

                    await vehicle.save()
                    r_dict['code'] = 1
                else:
                    if not title:
                        r_dict['code'] = -1
                    if not category:
                        r_dict['code'] = -2
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class VehicleDeleteViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def post(self, vehicle_id):
        r_dict = {'code': 0}
        try:
            await Vehicle.delete_by_ids([vehicle_id])
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class VehicleStatusSwitchViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def post(self, vehicle_id):
        r_dict = {'code': 0}
        try:
            status = self.get_argument('status', False)
            if status == 'true':
                status = STATUS_VEHICLE_ACTIVE
            else:
                status = STATUS_VEHICLE_INACTIVE
            vehicle = await Vehicle.get_by_id(vehicle_id)
            if vehicle:
                vehicle.status = status
                vehicle.updated_dt = datetime.datetime.now()
                vehicle.updated_id = self.current_user.oid
                await vehicle.save()
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


class VehicleBatchOperationViewHandler(BaseHandler):
    @decorators.render_json
    @decorators.permission_required(PERMISSION_TYPE_VEHICLE_RELEASE_MANAGEMENT)
    async def post(self):
        r_dict = {'code': 0}
        try:
            vehicle_id_list = self.get_body_arguments('vehicle_id_list[]', [])
            if vehicle_id_list:
                operate = self.get_argument('operate', None)
                if operate is not None:
                    if int(operate) == 1:
                        update_requests = []
                        for vehicle_id in vehicle_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(vehicle_id)},
                                                             {'$set': {'status': STATUS_VEHICLE_ACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await Vehicle.update_many(update_requests)
                    elif int(operate) == 0:
                        update_requests = []
                        for vehicle_id in vehicle_id_list:
                            update_requests.append(UpdateOne({'_id': ObjectId(vehicle_id)},
                                                             {'$set': {'status': STATUS_VEHICLE_INACTIVE,
                                                                       'updated_dt': datetime.datetime.now(),
                                                                       'updated_id': self.current_user.oid}}))
                        await Vehicle.update_many(update_requests)
                    elif int(operate) == -1:
                        await Vehicle.delete_by_ids(vehicle_id_list)
            r_dict['code'] = 1
        except RuntimeError:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/backoffice/vehicle/list/', VehicleListViewHandler, name='backoffice_vehicle_list'),
    url(r'/backoffice/vehicle/add/', VehicleAddViewHandler, name='backoffice_vehicle_add'),
    url(r'/backoffice/vehicle/edit/([0-9a-zA-Z_]+)/', VehicleEditViewHandler, name='backoffice_vehicle_edit'),
    url(r'/backoffice/vehicle/delete/([0-9a-zA-Z_]+)/', VehicleDeleteViewHandler, name='backoffice_vehicle_delete'),
    url(r'/backoffice/vehicle/status_switch/([0-9a-zA-Z_]+)/', VehicleStatusSwitchViewHandler,
        name='backoffice_vehicle_status_switch'),
    url(r'/backoffice/vehicle/batch_operate/', VehicleBatchOperationViewHandler,
        name='backoffice_vehicle_batch_operate')
]
