# !/usr/bin/python
# -*- coding:utf-8 -*-

import asyncio
import json
import os

import settings as ss
from caches.redis_utils import RedisCache
from commons import common_utils
from commons.common_utils import md5, read_json_resource, download_qr_image
from commons.request_utils import do_http_request
from db import STATUS_USER_ACTIVE, models, STATUS_SUBJECT_DIMENSION_ACTIVE, \
    CATEGORY_UPLOAD_FILE_IMG_GAME_MEMBER_SOURCE_QR, SOURCE_TYPE_MEMBER_DICT
from db import TYPE_DAN_GRADE_DICT, DAN_STAR_GRADE_MAPPING, STATUS_GAME_DAN_GRADE_ACTIVE
from db.models import User, AdministrativeDivision, VehicleAttribute, SubjectDimension, MemberDailyDimensionStatistics, \
    MemberLearningDayDimensionStatistics, GameMemberSource, UploadFiles, GameDanGrade, SubjectChoiceRules
from enums import ALL_PERMISSION_TYPE_LIST, KEY_INCREASE_USER, KEY_ADMINISTRATIVE_DIVISION, KEY_CACHE_WECHAT_TOWN
from motorengine import DocumentMetaclass, ASC, IndexModel
from wechat import API_MENU_CREATE_URL
from wechat.wechat_utils import get_access_token


async def init_indexes():
    """
    初始化索引
    :return:
    """
    model_list = []
    attributes = vars(models)
    if attributes:
        for name, attribute in attributes.items():
            if name not in ['SyncDocument', 'AsyncDocument', 'Document', 'BaseModel'] \
                    and attribute.__class__ == DocumentMetaclass:
                model_list.append((name, attribute))
    if model_list:
        for name, model in model_list:
            result = await model.create_indexes()
            if result:
                print('Model [%s] indexes create succeed!' % name)


async def init_dynamic_indexes():
    await init_member_daily_dimension_statistics_indexes()
    print('Model [MemberDailyDimensionStatistics Dimension] indexes create succeed!')
    await init_member_learning_day_dimension_statistics_indexes()
    print('Model [MemberLearningDayDimensionStatistics Dimension] indexes create succeed!')


async def init_member_daily_dimension_statistics_indexes():
    """
    创建自然日会员维度统计索引
    :return:
    """
    dimension_cursor = SubjectDimension.find(dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).sort(
        [('ordered', ASC)])
    indexes = []
    while await dimension_cursor.fetch_next:
        dimension = dimension_cursor.next_object()
        if dimension:
            cid = dimension.cid
            indexes.append(IndexModel([('dimension.%s' % cid, ASC)]))
    if indexes:
        await MemberDailyDimensionStatistics().get_async_collection().create_indexes(indexes)


async def init_member_learning_day_dimension_statistics_indexes():
    """
    创建学习日会员维度统计索引
    :return:
    """
    dimension_cursor = SubjectDimension.find(dict(status=STATUS_SUBJECT_DIMENSION_ACTIVE, parent_cid=None)).sort(
        [('ordered', ASC)])
    indexes = []
    while await dimension_cursor.fetch_next:
        dimension = dimension_cursor.next_object()
        if dimension:
            cid = dimension.cid
            indexes.append(IndexModel([('dimension.%s' % cid, ASC)]))
    if indexes:
        await MemberLearningDayDimensionStatistics().get_async_collection().create_indexes(indexes)


async def init_users():
    """
    初始化用户信息
    :return:
    """

    user = await User.find_one(dict(login_name='admin'))
    if user:
        await user.delete()

    user = User()
    user.code = common_utils.get_increase_code(KEY_INCREASE_USER)
    user.name = '超级管理员'
    user.email = '943738808@qq.com'  # 邮箱
    user.mobile = '15106139173'  # 手机
    user.superuser = True  # 是否为超管
    user.login_name = 'ycf'  # 用户名
    user.login_password = md5('123456')  # 密码
    user.status = STATUS_USER_ACTIVE  # 状态
    user.content = '超级管理员，无所不能'  # 备注
    user.permission_code_list = ALL_PERMISSION_TYPE_LIST

    oid = await user.save()
    if oid:
        print('Initialize user [', user.name, '] succeed!')


async def init_administrative_division():
    """
    初始化行政区划
    :return:
    """

    def generate_ad_models(division_list, parent_code=None, model_list=None):
        if division_list:
            for dd in division_list:
                post_code = dd['code']
                name = dd['name']
                en_name = dd['en_name']
                level = dd['level']
                if not name == '县' and not name == '市辖区':
                    ad = AdministrativeDivision()
                    ad.code = post_code
                    ad.title = name
                    ad.en_title = en_name
                    ad.level = level
                    ad.parent_code = parent_code
                    if model_list is None:
                        model_list = []
                    model_list.append(ad)
                c_division_list = dd.get('cell')
                if c_division_list:
                    generate_ad_models(c_division_list, post_code, model_list)

    # 清除行政区划内容
    await AdministrativeDivision.delete_many(dict(record_flag=1))
    RedisCache.delete(KEY_ADMINISTRATIVE_DIVISION)
    RedisCache.delete(KEY_CACHE_WECHAT_TOWN)

    with open(os.path.join(ss.SITE_ROOT, 'res', 'division.json'), encoding='utf-8') as json_file:
        json_s = json_file.read()
        division_dict = json.loads(json_s)
        if division_dict:
            result_list = []
            generate_ad_models(division_dict.get('division'), model_list=result_list)
            if result_list:
                oid_list = await AdministrativeDivision.insert_many(result_list)
                print('Initialize AD [', len(oid_list), '] succeed!')


async def init_attribute():
    result = read_json_resource('attribute.json')

    def get_attribute_doc(attr_type):
        attribute_docs = result.get(attr_type)
        if attribute_docs:
            return attribute_docs
        return []

    # 清除系统属性内容
    await VehicleAttribute.delete_many(dict(record_flag=1))

    if result:
        insert_doc_list = get_attribute_doc('vehicle_category')
        insert_doc_list.extend(get_attribute_doc('vehicle_brand'))
        insert_doc_list.extend(get_attribute_doc('vehicle_series'))
        insert_doc_list.extend(get_attribute_doc('vehicle_cfg'))
        insert_doc_list.extend(get_attribute_doc('vehicle_colour'))
        insert_doc_list.extend(get_attribute_doc('vehicle_displace'))
        if insert_doc_list:
            va_list = []
            for insert_doc in insert_doc_list:
                if insert_doc:
                    va = VehicleAttribute()
                    va.code = insert_doc.get('code')
                    va.title = insert_doc.get('title')
                    va.category = insert_doc.get('category')
                    va.parent_code = insert_doc.get('parent_code')
                    va_list.append(va)
            if va_list:
                inserted_ids = await VehicleAttribute.insert_many(va_list)
                print('Initialize vehicle properties [', len(inserted_ids), '] succeed!')


async def init_wechat_menu():
    menu_json = json.dumps(read_json_resource('wechat_menu.json'), ensure_ascii=False).encode('utf-8')
    access_token = get_access_token()
    menu_create_api = API_MENU_CREATE_URL % access_token
    response = await do_http_request(menu_create_api, method='POST', body=menu_json)
    result = json.loads(response.body)
    if result.get('errcode') == 0:
        print('Initialize wechat menu succeed!')
        return
    print('Initialize wechat menu failed [%s]!' % result)


async def init_source():
    """固化初始来源"""
    try:
        for k, v in SOURCE_TYPE_MEMBER_DICT.items():
            source = GameMemberSource(code=str(k), title=v)
            name = md5(v) + '.png'

            # 前三个有二维码
            if k <= 3:
                qr_path = ss.STATIC_PATH + '/files/' + name
                await download_qr_image(name, scene=str(k))

                qr_file = UploadFiles()
                qr_file.code = 'qr_' + source.code
                qr_file.title = name
                qr_file.source_title = source.title
                qr_file.category = CATEGORY_UPLOAD_FILE_IMG_GAME_MEMBER_SOURCE_QR
                qr_file.size = os.path.getsize(qr_path)
                await qr_file.save()

                source.qr_code_cid = qr_file.oid
                source.need_qr_code = True

            await source.save()
            print('init member source success.')
    except Exception:
        import traceback
        print(traceback.format_exc())
        print('init member source failed.')


async def init_dan_grade():
    rules = await SubjectChoiceRules.find({}).sort('quantity').to_list(None)
    for index, level in enumerate(TYPE_DAN_GRADE_DICT):
        if not await GameDanGrade.find_one({'index': level}):
            rule_cid = rules[index].cid if len(rules) > index else rules[-1].cid
            dan = GameDanGrade(index=level, title=TYPE_DAN_GRADE_DICT.get(level),
                               unlock_stars=DAN_STAR_GRADE_MAPPING.get(level), status=STATUS_GAME_DAN_GRADE_ACTIVE,
                               rule_cid=rule_cid)
            await dan.save()


task_list = [
    # init_administrative_division()
    init_users(),
    # init_administrative_division(),
    # init_attribute(),
]
loop = asyncio.get_event_loop()
loop.run_until_complete(asyncio.wait(task_list))
loop.close()
