# !/usr/bin/python
# -*- coding:utf-8 -*-
import sys
from datetime import datetime

import math

from caches.redis_utils import RedisCache
from commons.decorators import lazy_property
from db import STATUS_USER_LIST, SEX_LIST, STATUS_ROLE_LIST, STATUS_USER_ACTIVE, STATUS_ROLE_ACTIVE, \
    TYPE_DAN_GRADE_LIST, TYPE_STAR_GRADE_LIST, SOURCE_MEMBER_INTEGRAL_LIST, \
    STATUS_MEMBER_SURVEY_LIST, STATUS_RESULT_GAME_PK_LIST, STATUS_RESULT_GAME_PK_GIVE_UP, \
    STATUS_QUESTIONNAIRE_LIST, STATUS_QUESTIONNAIRE_ACTIVE, PUSH_CATEGORY_LIST, STATUS_PULL_ACTION_LIST, \
    CATEGORY_ATTRIBUTE_INFO_LIST, STATUS_VEHICLE_LIST, STATUS_VEHICLE_ACTIVE, CATEGORY_PRESENT_LIST, \
    STATUS_PRESENT_LIST, STATUS_DISCOUNT_COUPON_LIST, STATUS_DISCOUNT_COUPON_UNUSED, STATUS_EXCHANGE_ORDER_LIST, \
    CODE_CARRIER_LIST, CODE_SUBJECT_DIFFICULTY_LIST, CATEGORY_SUBJECT_KNOWLEDGE_LIST, CATEGORY_UPLOAD_FILE_LIST, \
    CATEGORY_UPLOAD_FILE_OTHER, STATUS_SUBJECT_LIST, STATUS_SUBJECT_ACTIVE, SOURCE_MEMBER_DIAMOND_LIST, SEX_DICT, \
    TYPE_EDUCATION_LIST, TYPE_AGE_GROUP_LIST, DIMENSION_SUBJECT_LIST, KNOWLEDGE_FIRST_LEVEL_LIST, \
    KNOWLEDGE_SECOND_LEVEL_LIST, CATEGORY_SUBJECT_DIMENSION_WEIGHT_LIST, STATUS_SUBJECT_DIMENSION_LIST, \
    STATUS_SUBJECT_CATEGORY_LIST, STATUS_SUBJECT_DIFFICULTY_LIST, STATUS_GAME_DAN_GRADE_LIST, \
    STATUS_GAME_CHECK_POINT_LIST, STATUS_SUBJECT_CHOICE_RULE_LIST, SOURCE_TYPE_MEMBER_SYSTEM, \
    STATUS_RESULT_CHECK_POINT_LIST, STATUS_RESULT_CHECK_POINT_GIVE_UP, SEX_NONE, TYPE_AGE_GROUP_NONE, \
    TYPE_EDUCATION_NONE, STATUS_WRONG_SUBJECT_ACTIVE, STATUS_WRONG_SUBJECT_LIST, MODULE_SEARCH_CONDITION_LIST, \
    STATUS_SUBJECT_DIMENSION_ACTIVE, STATUS_NOTICE_LIST, STATUS_NOTICE_UNREAD, CATEGORY_NOTICE_LIST, \
    CATEGORY_NOTICE_OTHER, CATEGORY_SUBJECT_LIST, CATEGORY_SUBJECT_GENERAL, CATEGORY_MEMBER_LIST, CATEGORY_MEMBER_NONE, \
    STATUS_MEMBER_SOURCE_INACTIVE, STATUS_MEMBER_SOURCE_LIST, CATEGORY_EXAM_CERTIFICATE_LIST, \
    CATEGORY_MEMBER_SHARE_LIST, CATEGORY_MEMBER_SHARE_OTHER, STATUS_RACE_LIST, CATEGORY_RACE_LOCAL, CATEGORY_RACE_LIST, \
    STATUS_UNIT_MANAGER_LIST, \
    STATUS_REDPACKET_AWARD_LIST, CAN_NOT_SEE_ALL_RACE, STATUS_LIST, CATEGORY_REDPACKET_RULE_LIST, \
    CATEGORY_REDPACKET_LIST, STATUS_REDPACKET_NOT_AWARDED, CATEGORY_MEMBER_COMMUNITY_RESIDENT, \
    MEMBER_TYPE_LIST, MEMBER_TYPE_NORMAL, TV_STATUS_LIST, TV_STATUS_ACTIVE, FILM_STATUS_LIST, FILM_STATUS_ACTIVE, \
    FILM_STATUS_INACTIVE
from motorengine import DESC
from motorengine.document import AsyncDocument, SyncDocument
from motorengine.fields import IntegerField, StringField, DateTimeField, ListField, BooleanField, DictField, FloatField


class BaseModel(AsyncDocument, SyncDocument):
    """
    基础模型
    """
    created_id = StringField()  # 创建_id
    created_dt = DateTimeField(default=datetime.now)  # 创建时间
    updated_id = StringField()  # 更新_id
    updated_dt = DateTimeField(default=datetime.now)  # 更新时间
    record_flag = IntegerField(default=1)  # 记录标记, 0: 无效的, 1: 有效的
    needless = DictField(default={})  # 冗余字段

    # 索引
    _indexes = [('created_dt', DESC), ('updated_dt', DESC), 'record_flag']


class InstantMail(BaseModel):
    mail_server = DictField(required=True)  # 邮件配置
    mail_from = StringField(required=True)  # 发件人
    mail_to = ListField(required=True)  # 收件人
    post_dt = DateTimeField(default=datetime.now)  # 邮件发送时间
    status = IntegerField(required=True)  # 状态
    subject = StringField(default='')  # 主题
    content = StringField(default='')  # 内容
    content_images = DictField(default={})  # 图片资源
    attachments = ListField(default=[])  # 附件

    exception = StringField()  # 异常信息

    _indexes = ['mail_from', 'mail_to', 'status', 'subject']


class InstantSms(BaseModel):
    sms_server = StringField(required=True)  # 短信服务
    account = StringField(required=True)  # 账号
    post_dt = DateTimeField(default=datetime.now)  # 发送时间
    status = IntegerField(required=True)  # 状态
    mobile = StringField(default='')  # 手机号
    content = StringField(default='')  # 内容

    exception = StringField()  # 异常信息

    _indexes = ['sms_server', 'account', 'status', 'post_dt', 'mobile']


class AdministrativeDivision(BaseModel):
    """
    行政区划
    """
    code = StringField(db_field='post_code', required=True)  # 区划编号（邮编）
    parent_code = StringField(default=None)  # 父级区划编号
    title = StringField(required=True)  # 区划名
    en_title = StringField()  # 区划英文名
    level = StringField()  # 所属行政级别（P：省，C：市，D：区、县）

    @lazy_property
    async def parent(self):
        """
        父级行政区划
        :return:
        """
        if self.parent_code:
            return await AdministrativeDivision.find_one(dict(code=self.parent_code))
        return None

    async def children(self, filter_code_list=None):
        """
        筛选子一级行政区划
        :param filter_code_list: 筛选的子集code
        :return:
        """
        if filter_code_list:
            if not isinstance(filter_code_list, list):
                raise ValueError('"filter_code_list" must be a tuple or list.')
        match = {
            'parent_code': self.code
        }
        if filter_code_list:
            match['code'] = {'$in': filter_code_list}
        return await AdministrativeDivision.find(match).to_list(None)

    # 索引
    _indexes = ['code', 'parent_code', 'title', 'en_title', 'level']


class UploadFiles(BaseModel):
    code = StringField(required=True, max_length=64)  # 文件编号
    title = StringField(required=True, max_length=64)  # 文件名
    source_title = StringField(required=True, max_length=256)  # 源标题
    category = IntegerField(default=CATEGORY_UPLOAD_FILE_OTHER, choice=CATEGORY_UPLOAD_FILE_LIST)  # 类别
    content_type = StringField()  # 附件类型
    size = IntegerField(required=True)  # 文件大小

    _indexes = ['code', 'category', 'size']


class User(BaseModel):
    """
    用户
    """
    code = StringField()  # 用户编号
    name = StringField()  # 用户姓名
    sex = IntegerField(choice=SEX_LIST)  # 性别
    email = StringField()  # 电子邮箱
    mobile = StringField(max_length=24)  # 手机号
    phone = StringField(max_length=24)  # 固话
    status = IntegerField(default=STATUS_USER_ACTIVE, choice=STATUS_USER_LIST)  # 状态
    content = StringField()  # 备注
    superuser = BooleanField(default=False)  # 是否超管

    login_name = StringField(required=True, max_length=64)  # 登录名
    login_password = StringField(required=True, max_length=32)  # 登录密码
    login_times = IntegerField(default=0)  # 登录次数
    login_datetime = DateTimeField(default=datetime.now)  # 最近登录时间
    access_secret_id = StringField(max_length=32)  # Access Secret ID
    access_secret_key = StringField(max_length=128)  # Access Secret KEY

    permission_code_list = ListField(default=[])  # 拥有的权限
    role_code_list = ListField(default=[])  # 所属的角色

    manage_region_code_list = ListField(default=[])  # 可管理的地区
    city = StringField()  # 城市标题
    province = StringField()  # 省份标题
    __lazy_all_permission_code_list = None
    __lazy_role_list = None

    def has_perm_sync(self, perm_code):
        """
        判断是否有对应的权限(同步的)
        :param perm_code: 权限编码或编码LIST或编码TUPLES
        :return: True or False
        """
        if perm_code:
            if self.superuser:
                return True
            if isinstance(perm_code, (tuple, list)):
                code_list = perm_code
            else:
                code_list = [perm_code]
            for code in code_list:
                all_permission_codes = self.__lazy_all_permission_code_list
                perm = self.superuser or (all_permission_codes and code in all_permission_codes)
                if perm:
                    return True
        return False

    async def has_perm(self, perm_code):
        """
        判断是否有对应的权限
        :param perm_code: 权限编码或编码LIST或编码TUPLES
        :return: True or False
        """
        if perm_code:
            if self.superuser:
                return True
            if isinstance(perm_code, (tuple, list)):
                code_list = perm_code
            else:
                code_list = [perm_code]
            for code in code_list:
                all_permission_codes = await self.all_permission_codes()
                perm = self.superuser or (all_permission_codes and code in all_permission_codes)
                if perm:
                    return True
        return False

    async def all_permission_codes(self):
        """
        用户所有权限编号
        :return:
        """
        if self.__lazy_all_permission_code_list is not None:
            return self.__lazy_all_permission_code_list
        self.__lazy_all_permission_code_list = []
        if self.permission_code_list:
            self.__lazy_all_permission_code_list.extend(self.permission_code_list)
        role_list = await self.roles_list()
        if role_list:
            for role in role_list:
                if role and role.permission_code_list:
                    self.__lazy_all_permission_code_list.extend(role.permission_code_list)
        return self.__lazy_all_permission_code_list

    async def roles_list(self):
        """
        所属所有角色
        :return:
        """
        if self.__lazy_role_list is not None:
            return self.__lazy_role_list
        self.__lazy_role_list = await Role.find(
            dict(code={'$in': self.role_code_list}, status=STATUS_ROLE_ACTIVE)).to_list(length=None)
        return self.__lazy_role_list

    _indexes = ['code', 'email', 'status', 'login_name', 'login_password', 'access_secret_id',
                'access_secret_key', 'permission_code_list', 'role_code_list']


class UserSearchCondition(BaseModel):
    """
    检索条件
    """
    user_cid = StringField(required=True)  # 用户CID
    module = IntegerField(required=True, choice=MODULE_SEARCH_CONDITION_LIST)  # 模块
    conditions = DictField()  # 检索条件

    _indexes = ['user_cid', 'module']


class Role(BaseModel):
    """
    角色
    """
    code = StringField(required=True)  # 角色编码
    title = StringField(required=True)  # 角色名
    status = IntegerField(default=STATUS_ROLE_ACTIVE, choice=STATUS_ROLE_LIST)  # 状态
    permission_code_list = ListField(default=[])  # 角色权限列表
    content = StringField()  # 备注

    _indexes = ['code', 'status']


class Member(BaseModel):
    """
    会员
    """
    code = StringField()  # 会员编号
    name = StringField()  # 会员姓名
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    email = StringField()  # 电子邮箱
    mobile = StringField(max_length=24)  # 手机号
    phone = StringField(max_length=24)  # 固话
    birthday = DateTimeField()  # 出生日期
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    status = IntegerField(default=STATUS_USER_ACTIVE, choice=STATUS_USER_LIST)  # 状态
    province_code = StringField(max_length=8)  # 省份编码
    city_code = StringField(max_length=8)  # 城市编码
    district_code = StringField(max_length=8)  # 区域编码
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度
    source = StringField(default=SOURCE_TYPE_MEMBER_SYSTEM)  # 用户来源
    category = IntegerField(default=CATEGORY_MEMBER_COMMUNITY_RESIDENT, choice=CATEGORY_MEMBER_LIST)  # 群体

    login_times = IntegerField(default=0)  # 登录次数
    login_datetime = DateTimeField(None)  # 最后登录时间

    # 微信
    union_id = StringField()  # 用户
    open_id = StringField()  # 用户OpenID
    nick_name = StringField()  # 微信昵称
    avatar = StringField()  # 头像
    auth_address = DictField()  # 授权的地理信息
    race_privilege = IntegerField(default=CAN_NOT_SEE_ALL_RACE)  # 是否有可以查看所有竞赛的特权
    wechat_info = DictField()  # 微信授权获取的信息

    # 奖励
    integral = IntegerField(default=0)  # 积分数
    diamond = IntegerField(default=0)  # 钻石数

    register_datetime = DateTimeField(default=datetime.now)

    # 车辆信息
    vehicle_code = StringField()  # 车型编号
    purchase_datetime = DateTimeField()  # 车辆购买时间
    vin = StringField(max_length=17)  # 车架号

    # 调查
    survey_times = IntegerField(default=0)  # 答题次数

    # 小游戏
    dan_grade = IntegerField()  # 段位下标
    star_grade = IntegerField(choice=TYPE_STAR_GRADE_LIST)  # 当前星数
    fight_times = IntegerField(default=0)  # PK次数
    win_percent = FloatField(default=0.0, min_value=0.0, max_value=100.0)  # 胜率
    win_times = IntegerField(default=0)  # 胜场
    highest_win_times = IntegerField(default=0)  # 最高连胜次数

    check_point_id = StringField()  # 关卡
    content = StringField()  # 备注

    _indexes = ['code', 'mobile', 'phone', 'status', 'source', 'union_id', 'open_id', 'vehicle_code',
                'province_code', 'sex', 'city_code', 'district_code', 'age_group', 'education', 'category']

    @property
    def sex_display(self, secret=False):
        if secret:
            return '保密'
        return SEX_DICT.get(self.sex, '-')

    @lazy_property
    def age(self):
        if isinstance(self.birthday, datetime):
            days = (datetime.now() - self.birthday).days
            age = int(math.floor(days / 365))
        else:
            age = 0
        return age

    @lazy_property
    def birth(self):
        if isinstance(self.birthday, datetime):
            return self.birthday.strftime('%Y-%m-%d')
        else:
            return ''

    async def save(self, session=None, **kwargs):
        if self.oid:
            open_id = RedisCache.get('mid_%s' % str(self.oid))
            if open_id:
                RedisCache.delete(open_id)
        await super(Member, self).save(session=None, **kwargs)


class MemberStarsAwardHistory(BaseModel):
    member_cid = StringField(required=True)  # Member.cid
    dan_grade = IntegerField(required=True, choice=TYPE_DAN_GRADE_LIST)  # 奖励段位
    quantity = IntegerField(default=0)  # 奖励数量
    award_dt = DateTimeField(default=datetime.now)  # 奖励时间

    _indexes = ['member_cid', 'dan_grade', 'award_dt']


class MemberFriend(BaseModel):
    """
    会员好友
    """
    member_cid = StringField(required=True)  # Member.cid
    friend_cid = StringField(required=True)  # Member.cid

    _indexes = ['member_cid', 'friend_cid']


class MemberIntegralDetail(BaseModel):
    """
    积分奖励详情
    """
    member_cid = StringField(required=True)  # 会员ID
    integral = IntegerField()  # 奖励积分
    source = IntegerField(choice=SOURCE_MEMBER_INTEGRAL_LIST)  # 积分奖励
    reward_datetime = DateTimeField(default=datetime.now)  # 奖励时间
    content = StringField()  # 备注

    _indexes = ['member_cid', 'source', ('reward_datetime', DESC)]


class MemberIntegralSource(BaseModel):
    """
    会员积分来源
    """
    source = IntegerField(choice=SOURCE_MEMBER_INTEGRAL_LIST)  # 来源
    integral = IntegerField(default=0)  # 奖励积分数

    _indexes = ['source', 'integral']


class MemberSurveyHistory(BaseModel):
    """
    会员调研历史
    """
    member_cid = StringField(required=True)  # 会员ID
    action_cid = StringField(required=True, max_length=32)  # 调研活动ID
    start_datetime = DateTimeField()  # 调研开始日期
    end_datetime = DateTimeField()  # 调研完成日期
    status = IntegerField(choice=STATUS_MEMBER_SURVEY_LIST)  # 状态

    _indexes = ['member_cid', 'action_cid', 'start_datetime', 'end_datetime', 'status']


class MemberGameHistory(BaseModel):
    """
    会员游戏PK历史

    result = [
        {
            'subject_cid': u'问卷编号',
            'selected_option_cid': u'选项编号',
            'consume_time':u'耗时（单位：s）',
            'score': 200,
            'true_answer': True
        },{
            'subject_cid': u'问卷编号',
            'selected_option_cid': u'选项编号',
            'consume_time':u'耗时（单位：s）',
            'score': 200
        }
    ]
    """
    member_cid = StringField(required=True)  # 会员ID
    result = ListField(default=[])  # PK结果DICT
    status = IntegerField(default=STATUS_RESULT_GAME_PK_GIVE_UP, choice=STATUS_RESULT_GAME_PK_LIST)  # PK状态
    fight_datetime = DateTimeField(default=datetime.now)  # 对战时间
    dan_grade = IntegerField(choice=TYPE_DAN_GRADE_LIST)  # 对战时所属的段位
    score = IntegerField(default=0)  # 得分
    runaway_index = IntegerField()  # 逃跑题目Index
    continuous_win_times = IntegerField(default=0)  # 当前连胜次数

    _indexes = ['member_cid', 'status', 'fight_datetime', 'dan_grade']


class MemberCheckPointHistory(BaseModel):
    """
    会员游戏竞赛历史

    result = [
        {
            'subject_cid': u'问卷编号',
            'selected_option_cid': u'选项编号',
            'consume_time':u'耗时（单位：s）',
            'score': 200,
            'true_answer': True
        }
    ]
    """
    member_cid = StringField(required=True)  # 会员ID
    result = ListField(default=[])  # 结果DICT
    status = IntegerField(default=STATUS_RESULT_CHECK_POINT_GIVE_UP, choice=STATUS_RESULT_CHECK_POINT_LIST)  # 竞赛状态
    check_point_cid = StringField()  # 关卡CID
    fight_datetime = DateTimeField(default=datetime.now)  # 竞赛时间
    score = IntegerField(default=0)  # 得分

    _indexes = ['member_cid', 'status', 'check_point_cid', 'fight_datetime']


class MemberExamHistory(BaseModel):
    """
    会员测试历史
    """
    member_cid = StringField(required=True)  # 会员ID
    result = ListField(default=[])  # 结果D
    category = IntegerField(required=True, choice=CATEGORY_SUBJECT_LIST)  # 类别
    exam_datetime = DateTimeField(default=datetime.now)  # 测试时间
    remain_time = IntegerField()  # 剩余时间, 单位: 秒
    accuracy = FloatField(default=0)  # 正确率

    _indexes = ['member_cid', 'exam_datetime', ('accuracy', DESC)]


class MemberExamCertificate(BaseModel):
    """
    会员测试获取的证书
    """
    member_cid = StringField(required=True)  # 会员cid
    history_cid = StringField(required=True)  # MemberExamHistory.cid
    award_dt = DateTimeField(default=datetime.now)  # 获取证书时间
    category = IntegerField(required=True, choice=CATEGORY_EXAM_CERTIFICATE_LIST)  # 证书类型

    _indexes = ['member_cid', 'history_cid', 'award_dt', 'category']


class MemberWrongSubject(BaseModel):
    """
    错题本
    """
    member_cid = StringField(required=True)  # 会员CID
    subject_cid = StringField(required=True)  # 题目CID
    option_cid = StringField(required=True)  # 答案CID
    status = IntegerField(default=STATUS_WRONG_SUBJECT_ACTIVE, choice=STATUS_WRONG_SUBJECT_LIST)
    wrong_dt = DateTimeField(default=datetime.now)  # 做错时间

    _indexes = ['member_cid', 'subject_cid', 'wrong_dt']


class Questionnaire(BaseModel):
    """
    调查问卷
    """
    code = StringField(required=True, max_length=32)
    title = StringField(required=True, max_length=128)
    url = StringField()
    process_url = StringField()  # 进度链接
    report_url = StringField()  # 报告链接
    download_url = StringField()  # 下载链接
    status = IntegerField(default=STATUS_QUESTIONNAIRE_ACTIVE, choice=STATUS_QUESTIONNAIRE_LIST)

    _indexes = ['code', 'status']


class SurveyActivity(BaseModel):
    """
    调研活动
    """
    code = StringField(required=True, max_length=32)  # 活动code
    title = StringField(required=True, max_length=256)  # 标题 Questionnaire.code
    q_cid = StringField(required=True)  # 问卷编号
    sample_amount = IntegerField(default=0)  # 样本回收数
    pushed_amount = IntegerField(default=0)  # 推送会员数量
    content = StringField()  # 描述

    _indexes = ['code', 'q_cid', 'sample_amount', 'pushed_amount']


class SurveyPushAction(BaseModel):
    """
    调研推送
    """
    activity_cid = StringField(required=True)  # 活动ID SurveyActivity.cid
    title = StringField(required=True)  # 标题
    q_cid = StringField(required=True)  # 问卷ID Questionnaire.cid
    cover = StringField()  # 海报（配图）
    category = IntegerField(required=True, choice=PUSH_CATEGORY_LIST)  # 推送方式
    status = IntegerField(choice=STATUS_PULL_ACTION_LIST)  # 活动状态
    push_datetime = DateTimeField(default=datetime.now)  # 推送时间
    pull_types = ListField()  # 客户端类型
    start_datetime = DateTimeField()  # 有效期开始
    end_datetime = DateTimeField()  # 有效期截至
    vehicle_code = StringField()  # 车型编号 Vehicle.code
    pushed_member_cid_list = ListField(default=[])  # 已推送会员 Member.cid
    all_member_cid_list = ListField(default=[])  # 需要推送的会员 Member.cid
    sample_amount = IntegerField(default=0)  # 样本回收数
    content = StringField()  # 备注

    _indexes = ['activity_cid', 'q_cid', 'category', 'status', ('push_datetime', DESC), 'vehicle_code']


class VehicleAttribute(BaseModel):
    """
    车型属性
    """
    code = StringField(max_length=32)  # 属性编码
    title = StringField(max_length=128)  # 属性名称
    parent_code = StringField(max_length=32)  # 父属性编码
    category = IntegerField(choice=CATEGORY_ATTRIBUTE_INFO_LIST)  # 属性类别

    _indexes = ['code', 'parent_code', 'category']


class Vehicle(BaseModel):
    """
    车型
    """
    code = StringField(max_length=32)  # 车辆编码
    title = StringField(max_length=128)  # 车辆名称
    category = StringField(max_length=32)  # 车辆类别 VehicleAttribute.code
    brand = StringField(max_length=32)  # 车辆品牌 VehicleAttribute.code
    series = StringField(max_length=32)  # 车辆系列 VehicleAttribute.code
    config = StringField(max_length=32)  # 车辆配置 VehicleAttribute.code
    colour = StringField(max_length=32)  # 车辆颜色 VehicleAttribute.code
    displace = StringField(max_length=32)  # 车辆排量 VehicleAttribute.code
    year = StringField(max_length=32, default='')  # 车辆年份 VehicleAttribute.code
    status = IntegerField(default=STATUS_VEHICLE_ACTIVE, choice=STATUS_VEHICLE_LIST)  # 状态
    content = StringField()  # 备注

    _indexes = ['code', 'category', 'brand', 'series', 'config', 'colour', 'displace', 'status']


class Present(BaseModel):
    """
    礼品
    """
    code = StringField(required=True, max_length=64)  # 礼品编号
    title = StringField(required=True, max_length=256)  # 礼品名称
    category = IntegerField(choice=CATEGORY_PRESENT_LIST)  # 礼品类别
    placard = StringField()  # 礼品海报（封面）
    ex_integral = IntegerField(default=sys.maxsize)  # 兑换所需积分
    inventory = IntegerField(default=0)  # 库存量
    details = StringField()  # 详情
    status = IntegerField(choice=STATUS_PRESENT_LIST)  # 状态
    start_date = DateTimeField()  # 有效期起
    end_date = DateTimeField()  # 有效期止
    limit = IntegerField(default=0)  # 限领数量， 0：不限制
    exchanged = IntegerField(default=0)  # 已兑换数量
    lucky_price = FloatField(default=0.0)  # 红包面值
    sort = IntegerField(default=0)  # 顺序

    _indexes = ['code', 'category', 'ex_integral', 'inventory', 'status', ('start_date', DESC),
                ('end_date', DESC), 'sort']


class DiscountCoupon(BaseModel):
    """
    优惠券
    """
    member_cid = StringField()  # 会员编号 Member.cid
    present_cid = StringField(required=True)  # 礼品编号 Present.cid
    exchange_code = StringField()  # 订单编号 ExchangeOrder.code
    serial_num = StringField()  # 优惠券序列号
    status = IntegerField(default=STATUS_DISCOUNT_COUPON_UNUSED, choice=STATUS_DISCOUNT_COUPON_LIST)  # 优惠券状态

    _indexes = ['member_cid', 'present_cid', 'serial_num', 'exchange_code', 'status']


class ExchangeOrder(BaseModel):
    """
    订单
    """
    present_cid = StringField(required=True)  # 礼品编号.Present.cid
    code = StringField(required=True, max_length=128)  # 订单号
    order_datetime = DateTimeField(default=datetime.now)  # 订单生成时间
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    province_code = StringField()  # 省份编码 AdministrativeDivision.code
    city_code = StringField()  # 城市编码 AdministrativeDivision.code
    district_code = StringField()  # 区域编码 AdministrativeDivision.code
    receiver_name = StringField()  # 收货人姓名
    receiver_mobile = StringField()  # 收货人手机号
    receive_address = StringField()  # 收货地址
    ex_integral = IntegerField(default=0)  # 订单积分
    status = IntegerField(choice=STATUS_EXCHANGE_ORDER_LIST)  # 订单状态
    carrier_code = IntegerField(choice=CODE_CARRIER_LIST)  # 承运人编号
    shipped_code = StringField()  # 运单号

    _indexes = ['present_cid', 'code', 'order_datetime', 'member_cid', 'receiver_name', 'receiver_mobile',
                'status', 'shipped_code']


class Address(BaseModel):
    """
    收货地址
    """
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    province_code = StringField()  # 省份编码 AdministrativeDivision.code
    city_code = StringField()  # 城市编码 AdministrativeDivision.code
    district_code = StringField()  # 区域编码 AdministrativeDivision.code
    receiver_name = StringField()  # 收货人姓名
    receiver_mobile = StringField()  # 收货人手机号
    receive_address = StringField()  # 收货地址
    if_default = IntegerField(default=0)  # 是否默认

    _indexes = ['member_cid', 'province_code', 'city_code', 'district_code', 'receiver_name', 'receiver_mobile']


class Subject(BaseModel):
    """
    小程序题目
    """
    code = StringField(required=True)  # 题目编号
    custom_code = StringField()  # 客户定制题目编号
    title = StringField(required=True)  # 题目标题

    difficulty = IntegerField(choice=CODE_SUBJECT_DIFFICULTY_LIST)  # 题目难度
    category = IntegerField(choice=CATEGORY_SUBJECT_KNOWLEDGE_LIST)  # 题目类别
    dimension = IntegerField(choice=DIMENSION_SUBJECT_LIST)  # 知识维度 DIMENSION_SUBJECT_LIST

    image_cid = StringField()  # 图片 UploadFiles.cid
    status = IntegerField(default=STATUS_SUBJECT_ACTIVE, choice=STATUS_SUBJECT_LIST)  # 题目状态 STATUS_SUBJECT_LIST

    knowledge_first = IntegerField(choice=KNOWLEDGE_FIRST_LEVEL_LIST)  # 一级知识点 KNOWLEDGE_FIRST_LEVEL_LIST
    knowledge_second = IntegerField(choice=KNOWLEDGE_SECOND_LEVEL_LIST)  # 二级知识点 KNOWLEDGE_SECOND_LEVEL_LIST

    dimension_dict = DictField()  # 维度
    category_use = IntegerField(default=CATEGORY_SUBJECT_GENERAL, choice=CATEGORY_SUBJECT_LIST)  # 用途

    content = StringField()  # 备注
    resolving = StringField()  # 答案解析
    _indexes = ['code', 'custom_code', 'difficulty', 'category', 'status']


class SubjectOption(BaseModel):
    """
    小程序题目选项
    """
    subject_cid = StringField(required=True)  # 题目编号 Subject.cid
    code = StringField(required=True)  # 选项编号
    title = StringField(required=True)  # 选项标题
    correct = BooleanField(default=False)  # 是否为正确选项
    sort = IntegerField(default=0)  # 顺序

    _indexes = ['subject_cid', 'code', 'correct', 'sort']


class SubjectDimension(BaseModel):
    """
    题目维度
    """
    code = StringField(required=True)  # 维度编号
    title = StringField(required=True, max_length=32)  # 维度标题
    category = IntegerField(choice=CATEGORY_SUBJECT_DIMENSION_WEIGHT_LIST)  # 维度类别
    ordered = IntegerField(default=0)  # 顺序
    status = IntegerField(default=STATUS_SUBJECT_DIMENSION_ACTIVE, choice=STATUS_SUBJECT_DIMENSION_LIST)  # 状态
    parent_cid = StringField(max_length=32)  # 父级CID
    comment = StringField()  # 备注

    _indexes = ['category', 'status', 'ordered', 'parent_cid']


class SubjectCategory(BaseModel):
    """
    题目类别
    """
    title = StringField(required=True, max_length=32)  # 类别标题
    status = IntegerField(choice=STATUS_SUBJECT_CATEGORY_LIST)  # 类别状态
    comment = StringField()  # 备注

    _indexes = ['status']


class SubjectDifficulty(BaseModel):
    """
    题目难度
    """
    title = StringField(required=True, max_length=32)  # 类别标题
    status = IntegerField(choice=STATUS_SUBJECT_DIFFICULTY_LIST)  # 类别状态
    ordered = IntegerField(default=0)  # 顺序
    comment = StringField()  # 备注

    _indexes = ['status', 'ordered']


class SubjectChoiceRules(BaseModel):
    """
    抽题规则
    """
    code = StringField(required=True, max_length=32)  # 规则编号
    title = StringField(required=True, max_length=128)  # 规则标题
    quantity = IntegerField(default=0)  # 单局题目总数
    dimension_rules = DictField()  # 维度配置
    status = IntegerField(choice=STATUS_SUBJECT_CHOICE_RULE_LIST)  # 规则状态
    comment = StringField()  # 备注

    _indexes = ['code']


class SubjectBanks(BaseModel):
    """
    题库
    """
    rule_cid = StringField(required=True)  # 抽题规则CID, SubjectChoiceRules.cid
    quantity = IntegerField(default=1)  # 包含题目数
    subject_cid_list = ListField(required=True)  # 包含的题目编号，Subject.cid
    choice_dt = DateTimeField(default=datetime.now)  # 题目抽取时间

    _indexes = ['rule_cid', 'choice_dt']


class GameDanGrade(BaseModel):
    """
    游戏段位
    """
    index = IntegerField(required=True)  # 段位序号
    title = StringField(required=True)  # 段位名称
    # quantity = IntegerField(required=True)  # 当前段位题目数
    unlock_stars = IntegerField(required=True)  # 解锁星星数
    thumbnail = StringField()  # 缩略图 UploadFiles.cid
    status = IntegerField(choice=STATUS_GAME_DAN_GRADE_LIST)  # 段位状态
    rule_cid = StringField(required=True)  # 关联的抽题规则CID

    _indexes = ['index', 'status']


class GameDiamondReward(BaseModel):
    """
    游戏钻石奖励配置
    """
    source = IntegerField(required=True, choice=SOURCE_MEMBER_DIAMOND_LIST)  # 奖励来源
    quantity = IntegerField(required=True, default=0)  # 奖励钻石数

    _indexes = ['source']


class GameDiamondConsume(BaseModel):
    """
    游戏钻石消耗配置
    """
    source = IntegerField(required=True, choice=TYPE_DAN_GRADE_LIST)  # 奖励来源: TYPE_DAN_GRADE_LIST
    quantity = IntegerField(required=True, default=0)  # 消费积分

    _indexes = ['source']


class MemberDiamondDetail(BaseModel):
    """
    会员钻石奖励详情
    """
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    diamond = IntegerField(default=0)  # 奖励积钻石数
    source = IntegerField(choice=SOURCE_MEMBER_DIAMOND_LIST)  # 钻石奖励Code
    reward_datetime = DateTimeField(default=datetime.now)  # 奖励时间
    content = StringField()  # 备注

    _indexes = ['member_cid', 'source', 'diamond', 'reward_datetime']


class VaultDiamondBank(BaseModel):
    quantity = IntegerField(default=0)  # 奖励额度
    times = IntegerField(default=0)  # 日领取上限次数
    minutes = IntegerField(default=0)  # 时限（分）

    _indexes = ['quantity', 'times', 'minutes']


class MemberNotice(BaseModel):
    """
    会员通知
    """
    member_cid = StringField(required=True)  # Member.cid
    category = IntegerField(default=CATEGORY_NOTICE_OTHER, choice=CATEGORY_NOTICE_LIST)  # 类别
    status = IntegerField(default=STATUS_NOTICE_UNREAD, choice=STATUS_NOTICE_LIST)  # 状态
    notice_datetime = DateTimeField(default=datetime.now)  # 通知时间
    race_cid = StringField()  # 中奖信息相关的活动
    checkpoint_cid = StringField()  # 中奖关卡
    content = StringField(default=None)  # 内容

    _indexes = ['member_cid', 'category', 'status', 'notice_datetime', 'race_cid']


class GameMemberSource(BaseModel):
    """
    用户来源
    """
    code = StringField(required=True)  # 来源code
    title = StringField(required=True)  # 来源名称
    status = IntegerField(default=STATUS_MEMBER_SOURCE_INACTIVE, choice=STATUS_MEMBER_SOURCE_LIST)  # 状态
    need_qr_code = BooleanField(default=False)  # 需要使用二维码
    qr_code_cid = StringField(default=None)  # 二维码文件ID UploadFiles.cid
    locked = BooleanField(default=False)  # 是否锁定
    comment = StringField(default=None)

    _indexes = ['code', 'locked']


class DockingStatistics(BaseModel):
    """
    对接统计

    docking_code, member_cid：复合主键
    """
    docking_code = StringField(required=True)  # 接入标识，例如：20180425120000
    member_cid = StringField(required=True)  # Member.cid

    member_code = StringField(max_length=32)  # Member.code
    province_code = StringField()  # 省份编码
    city_code = StringField()  # 城市编码
    sex = IntegerField(choice=SEX_LIST)  # 性别
    age_group = IntegerField(choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(choice=TYPE_EDUCATION_LIST)  # 受教育程度

    total_times = IntegerField(default=0)  # 游戏累计次数
    total_subject_quantity = IntegerField(default=0)  # 游戏题目数
    total_subject_correct_quantity = IntegerField(default=0)  # 游戏正确题目数
    # 正确题目数量统计详情 {'0': 1, '1': 12, '3': 4, ...}
    correct_quantity_detail = DictField()
    # 题目统计详情 {'题目编号': {'total': 32, 'correct': 12}}
    subjects_detail = DictField()
    # 维度统计详情
    dimension_detail = DictField()

    _indexes = ['docking_code', 'member_code', 'province_code', 'city_code', 'sex', 'age_group', 'education']


class SubjectAccuracyStatistics(BaseModel):
    """
    游戏正确率统计
    """
    dimension = DictField()  # 维度统计
    age_group = DictField()  # 年龄段
    education = DictField()  # 受教育程度
    gender = DictField()  # 性别


class MemberAccuracyStatistics(BaseModel):
    """
    会员做题正确率统计
    """
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    # 对战
    total_times = IntegerField(default=0)  # 对战总场数
    win_times = IntegerField(default=0)  # 对战胜利场数
    lose_times = IntegerField(default=0)  # 对战失败场数
    escape_times = IntegerField(default=0)  # 对战逃跑场数
    tie_times = IntegerField(default=0)  # 对战平局场数
    # 做题
    total_quantity = IntegerField(default=0)  # 总答题目数
    correct_quantity = IntegerField(default=0)  # 答题正确数
    # 维度
    dimension = DictField()  # 维度统计信息

    _indexes = ['member_cid', 'total_times', 'lose_times', 'escape_times', 'tie_times', 'total_quantity',
                'correct_quantity']


class MemberDailyStatistics(BaseModel):
    """
    会员日常统计
    """
    daily_code = StringField(required=True)  # 日期code
    member_cid = StringField(required=True)  # 会员编号 Member.cid

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code

    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    learn_times = IntegerField(default=0)  # 学习总次数
    subject_total_quantity = IntegerField(default=0)  # 总题目数
    subject_correct_quantity = IntegerField(default=0)  # 总正确题目数

    quantity_detail = DictField()  # 正确题目数详情 {'0': 1, '1': 12, '3': 4, '4': 5, ...}
    dimension_detail = DictField()  # 维度详情 {'cid1': {'total':10, 'correct':9}, ...}

    _indexes = ['daily_code', 'member_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education']


class MemberLearningDayStatistics(BaseModel):
    """
    会员学习日统计
    """
    learning_code = IntegerField(required=True)  # 学习日code
    member_cid = StringField(required=True)  # 会员编号 Member.cid

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code

    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    learn_times = IntegerField(default=0)  # 学习总次数
    subject_total_quantity = IntegerField(default=0)  # 总题目数
    subject_correct_quantity = IntegerField(default=0)  # 总正确题目数

    quantity_detail = DictField()  # 正确题目数详情 {'0': 1, '1': 12, '3': 4, '4': 5, ...}
    dimension_detail = DictField()  # 维度详情 {'cid1': {'total':10, 'correct':9}, ...}

    _indexes = ['learning_code', 'member_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education']


class MemberSubjectStatistics(BaseModel):
    """
    题目正确率统计
    """
    subject_cid = StringField(required=True)  # 题目CID Subject.cid

    dimension = DictField(default=None)  # 维度信息
    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code

    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    total = IntegerField(default=0)  # 总答题次数
    correct = IntegerField(default=0)  # 正确答题次数
    accuracy = FloatField(default=0)  # 答题正确率

    _indexes = ['subject_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education', 'total', 'correct', 'accuracy']


class MemberDimensionStatistics(BaseModel):
    """
    维度统计
    """
    member_cid = StringField(required=True)  # 会员CID Member.cid
    dimension_cid = StringField(required=True)  # 维度CID SubjectDimension.cid

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code

    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    total = IntegerField(default=0)  # 总答题次数
    correct = IntegerField(default=0)  # 正确答题次数

    cross_dimension = DictField()  # {"cid":{'total':100, 'correct':90}}

    _indexes = ['member_cid', 'dimension_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education', 'total', 'correct']


class MemberSourceStatistics(BaseModel):
    daily_code = StringField(required=True)  # 日期code
    member_cid = StringField(required=True)  # 会员编号 Member.cid

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code

    source = StringField(default=SOURCE_TYPE_MEMBER_SYSTEM)  # 用户来源

    _indexes = ['daily_code', 'member_cid', 'province_code', 'city_code', 'source']


class MemberPropertyStatistics(BaseModel):
    """
    会员属性统计
    """
    daily_code = StringField(required=True)  # 日期code
    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code
    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度
    source = StringField(default=SOURCE_TYPE_MEMBER_SYSTEM)  # 来源

    quantity = IntegerField(default=0)  # 数量

    _indexes = ['daily_code', 'province_code', 'city_code', 'district_code', 'gender', 'age_group', 'education',
                'source', 'quantity']


class MemberDailyDimensionStatistics(BaseModel):
    """
    会员自然日维度统计
    """
    daily_code = StringField(required=True)  # 日期code
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    dimension = DictField(required=True)  # 维度信息

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code
    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    subject_total_quantity = IntegerField(default=0)  # 总题目数
    subject_correct_quantity = IntegerField(default=0)  # 总正确题目数

    _indexes = ['daily_code', 'member_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education']


class MemberLearningDayDimensionStatistics(BaseModel):
    """
    会员学习日维度统计
    """
    learning_code = IntegerField(required=True)  # 学习日code
    member_cid = StringField(required=True)  # 会员编号 Member.cid
    dimension = DictField(required=True)  # 维度信息

    province_code = StringField(default=None)  # 省份编码 AdministrativeDivision.code
    city_code = StringField(default=None)  # 城市编码 AdministrativeDivision.code
    district_code = StringField(default=None)  # 区、县编码 AdministrativeDivision.code
    gender = IntegerField(default=SEX_NONE, choice=SEX_LIST)  # 性别
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)  # 年龄段
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)  # 受教育程度

    subject_total_quantity = IntegerField(default=0)  # 总题目数
    subject_correct_quantity = IntegerField(default=0)  # 总正确题目数

    _indexes = ['learning_code', 'member_cid', 'province_code', 'city_code', 'district_code', 'gender', 'age_group',
                'education']


class FightRobotAnalysisReference(BaseModel):
    """
    排位赛机器人分析参考
    """
    subject_cid = StringField(required=True)  # 题目编号 Subject.cid

    gender = IntegerField(default=None)  # 性别
    age_group = IntegerField(default=None)  # 年龄段
    education = IntegerField(default=None)  # 受教育程度

    words = IntegerField(default=0)  # 题目字数

    total = IntegerField(default=0)  # 总次数
    correct = IntegerField(default=0)  # 正确次数
    accuracy = FloatField(default=0)  # 正确率

    avg_correct_seconds = FloatField(default=0)  # 平均正确答案时间
    avg_incorrect_seconds = FloatField(default=0)  # 平均正确答案时间

    _indexes = ['subject_cid', 'gender', 'age_group', 'education']


class MemberShareStatistics(BaseModel):
    """
    分享行为统计
    """
    member_cid = StringField(required=True)
    category = IntegerField(required=True, choice=CATEGORY_MEMBER_SHARE_LIST, default=CATEGORY_MEMBER_SHARE_OTHER)
    share_dt = DateTimeField(required=True, default=datetime.now)
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)
    province_code = StringField(default=None)
    city_code = StringField(default=None)


class SubjectWrongViewedStatistics(BaseModel):
    """
    错题本查看次数

    用户每查看一次加一
    """
    member_cid = StringField(required=True)
    count = IntegerField(default=0)
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)
    province_code = StringField(default=None)
    city_code = StringField(default=None)


class SubjectResolvingViewedStatistics(BaseModel):
    """
    答案解析查看统计
    """

    member_cid = StringField(required=True)
    check_dt = DateTimeField(required=True, default=datetime.now)
    wrong_count = IntegerField(required=True, default=0)  # 错题数
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)
    province_code = StringField(default=None)
    city_code = StringField(default=None)


class PersonalCenterViewedStatistics(BaseModel):
    """
    个人中心查看统计
    """
    member_cid = StringField(required=True)
    count = IntegerField(required=True, default=0)  # 查看次数
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)
    province_code = StringField(default=None)
    city_code = StringField(default=None)


class Race(BaseModel):
    """
    竞赛活动
    """

    code = StringField(required=True, max_length=16)
    title = StringField(required=True, max_length=32, min_length=4)
    category = IntegerField(default=CATEGORY_RACE_LOCAL, choice=CATEGORY_RACE_LIST)  # 活动分类
    province_code = StringField(required=True, default=None)
    city_code = StringField(default=None)
    start_datetime = DateTimeField(required=True)
    end_datetime = DateTimeField(required=True)
    image_cid = StringField()
    status = IntegerField(choice=STATUS_RACE_LIST)
    company_enabled = BooleanField(default=False)  # 是否启用单位
    resolving_enabled = BooleanField(default=False)  # 是否启用答案解析
    mobile_enabled = BooleanField(default=False)  # 是否需要电话号码
    mobile_before_race = BooleanField(default=False)  # 是否进入活动之前填写手机号码
    Mandatory_enabled = BooleanField(default=False)  # 单位是否必选
    play_quantity_enabled = BooleanField(default=False)  # 参与人数是否必选
    town_enable = BooleanField(default=False)  # 是否启用单位或乡镇
    # 红包周期 redpkt_start_dt == redpkt_end_dt ==> 没有配置红包
    redpkt_account = StringField()  # 红包账户
    redpkt_start_dt = DateTimeField()
    redpkt_end_dt = DateTimeField()

    guide = StringField()  # 活动说明
    owner_list = ListField(default=[])  # 所有者 User.cid

    _indexes = ['code', 'title', 'province_code', 'city_code', 'start_datetime', 'end_datetime']


class RaceSubjectRefer(BaseModel):
    """
    竞赛题目引用
    """

    race_cid = StringField(required=True)  # 竞赛cid
    subject_cid = StringField(required=True)
    title = StringField(required=True)
    status = IntegerField(default=STATUS_SUBJECT_ACTIVE, choice=STATUS_SUBJECT_LIST)  # 题目状态 STATUS_SUBJECT_LIST
    dimension_dict = DictField()  # 维度

    _indexes = ['race_cid', 'subject_cid']


class RaceGameCheckPoint(BaseModel):
    """
    游戏关卡
    """

    race_cid = StringField(required=True)  # 竞赛cid
    index = IntegerField(required=True)  # 关卡序号
    unlock_quantity = IntegerField(required=True)  # 解锁下一关所需答题正确数
    alias = StringField()  # 关卡别名
    status = IntegerField(choice=STATUS_GAME_CHECK_POINT_LIST)  # 关卡状态
    rule_cid = StringField(required=True)  # 关联的抽题规则CID
    redpkt_rule_cid = StringField()  # 红包规则的cid
    comment = StringField()  # 备注
    answer_limit_quantity = IntegerField()
    _indexes = ['index', 'status']


class RaceSubjectChoiceRules(BaseModel):
    """
    抽题规则
    """
    race_cid = StringField(required=True)  # 竞赛活动cid
    code = StringField(required=True, max_length=32)  # 规则编号
    title = StringField(required=True, max_length=64)  # 规则标题
    quantity = IntegerField(default=0)  # 单局题目总数
    dimension_rules = DictField()  # 维度配置
    status = IntegerField(choice=STATUS_SUBJECT_CHOICE_RULE_LIST)  # 规则状态
    comment = StringField()  # 备注

    _indexes = ['code', 'title']


class RaceSubjectBanks(BaseModel):
    """
    竞赛题库
    """
    race_cid = StringField(required=True)  # 竞赛活动的cid
    rule_cid = StringField(required=True)  # 抽题规则CID, SubjectChoiceRules.cid
    quantity = IntegerField(default=1)  # 包含题目数
    refer_subject_cid_list = ListField(required=True)  # 包含的题目编号，refer_Subject.cid
    choice_dt = DateTimeField(default=datetime.now)  # 题目抽取时间

    _indexes = ['rule_cid', 'choice_dt']


class RedPacketEntry(BaseModel):
    position = IntegerField(required=True)  # 奖品在奖池中的位置
    race_cid = StringField(required=True)  # 竞赛活动cid信息
    rule_cid = StringField(required=True)  # 红包规则cid信息
    award_cid = StringField(required=True)  # 奖品cid信息
    status = IntegerField(choice=STATUS_REDPACKET_AWARD_LIST)  # 是否被领取
    open_id = StringField()  # 领取人的open_id


class RedPacketBox(BaseModel):
    race_cid = StringField(required=True)  # 竞赛活动cid信息
    rule_cid = StringField(required=True)  # 红包规则cid信息
    award_cid = StringField()  # 奖品RedPacketItemSetting.cid信息，None == 谢谢惠顾
    award_msg = StringField()  # 奖励信息
    award_amount = FloatField(default=0.0)  # 奖励金额

    checkpoint_cid = StringField()  # 竞赛关卡cid
    draw_status = IntegerField(default=STATUS_REDPACKET_NOT_AWARDED, choice=STATUS_REDPACKET_AWARD_LIST)  # 是否被领取
    member_cid = StringField()  # 领取人的open_id
    draw_dt = DateTimeField()  # 领取时间, 领走
    redpkt_rid = StringField()  # 订单号
    request_dt = DateTimeField(default=datetime.now)  # 向红包平台请求发红包的时间， 拆的时间
    request_status = IntegerField()  # 请求是否成功
    # issue_status = IntegerField()  # 发放状态
    error_msg = StringField()  # 错误信息


class RedPacketBasicSetting(BaseModel):
    """
    抽奖的基础设置
    """
    race_cid = StringField(required=True)  # 竞赛活动的cid
    rule_cid = StringField(required=True)  # 红包规则cid
    expect_num = IntegerField(default=0)  # 预计人数
    top_limit = IntegerField(default=0)  # 每日中奖上限
    fail_msg = StringField(max_length=64)  # 未中奖提示语
    over_msg = StringField(max_length=64)  # 已达中奖上限提示语
    guide = StringField(max_length=128)  # 活动说明


class RedPacketItemSetting(BaseModel):
    """
    奖品设置
    """
    race_cid = StringField(required=True)  # 竞赛活动的cid
    rule_cid = StringField(required=True)  # 红包规则cid
    title = StringField(required=True)  # 奖品名称
    amount = FloatField(required=True)  # 红包金额(元)
    quantity = IntegerField(required=True)  # 奖品数量
    message = StringField(required=True)  # 提示语


class RedPacketLotteryHistory(BaseModel):
    """
    抽奖记录
    """
    race_cid = StringField(required=True)  # 竞赛活动的cid
    rule_cid = StringField(required=True)  # 红包规则的cid
    checkpoint_cid = StringField(required=True)  # 竞赛关卡的cid
    open_id = StringField(required=True)  # 用户open_id
    award_cid = StringField()  # 奖品的cid  为None时表示没有中奖
    lottery_dt = DateTimeField(required=True, default=datetime.now)  # 抽中奖励的时间


class RedPacketAwardHistory(BaseModel):
    """
    向红包平台请求发红包奖励的记录
    """
    redpacket_rid = StringField(required=True)  # 订单号
    award_cid = StringField(required=True)  # 奖品itemsetting.cid
    request_dt = DateTimeField(required=True, default=datetime.now)  # 向红包平台请求发红包的时间
    request_status = IntegerField(required=True)  # 请求是否成功
    issue_status = IntegerField()  # 发放状态
    error_msg = StringField()  # 错误信息


class RaceMapping(BaseModel):
    """
    会员竞赛相关信息
    """
    member_cid = StringField(required=True)
    race_cid = StringField(required=True)
    race_check_point_cid = StringField()  # 竞赛关卡
    college_id = StringField()
    category = IntegerField(default=CATEGORY_MEMBER_NONE, choice=CATEGORY_MEMBER_LIST)  # 群体
    age_group = IntegerField(default=TYPE_AGE_GROUP_NONE, choice=TYPE_AGE_GROUP_LIST)
    sex = IntegerField(default=SEX_NONE, choice=SEX_LIST)
    education = IntegerField(default=TYPE_EDUCATION_NONE, choice=TYPE_EDUCATION_LIST)

    # ------ no use --------
    diamond = IntegerField(default=0)  # 钻石数
    dan_grade = IntegerField()  # 段位.
    star_grade = IntegerField(default=0)  # 当前星数
    fight_times = IntegerField(default=0)  # PK次数
    win_percent = FloatField(default=0.0, min_value=0.0, max_value=100.0)  # 胜率
    win_times = IntegerField(default=0)  # 胜场
    lose_times = IntegerField(default=0)  # 对战失败场数
    escape_times = IntegerField(default=0)  # 对战逃跑场数
    tie_times = IntegerField(default=0)  # 对战平局场数
    highest_win_times = IntegerField(default=0)  # 最高连胜次数

    province_code = StringField(max_length=8)  # 省份编码
    city_code = StringField(max_length=8)  # 城市编码
    district_code = StringField(max_length=8)  # 区域编码
    auth_address = DictField()  # 授权的地理信息
    company_cid = StringField()  # 公司的cid
    mobile = StringField()  # 电话号码

    # 活动报表
    total_correct = IntegerField(default=0)  # 总的正确题目数量
    total_count = IntegerField(default=0)  # 总的题目数量

    _indexes = ['member_cid', 'race_cid', 'race_check_point_cid', 'province_code', 'city_code', 'category']


class Company(BaseModel):
    """
    公司单位
    """

    race_cid = StringField(required=True)  # 竞赛活动cid
    code = StringField(required=True, max_length=16)  # 单位编号
    title = StringField(required=True, max_length=64)  # 单位名称
    status = IntegerField(choice=STATUS_UNIT_MANAGER_LIST)  # 单位状态

    _indexes = ['race_cid', 'code', 'title']


class RedPacketRule(BaseModel):
    """
    红包规则
    """

    code = StringField(required=True, max_length=16)  # 规则编号
    title = StringField(required=True, max_length=32)  # 规则名称
    status = IntegerField(required=True, choice=STATUS_LIST)  # 启用状态
    race_cid = StringField(required=True, max_length=32)  # 活动cid
    category = IntegerField(required=True, choice=CATEGORY_REDPACKET_RULE_LIST)  # 红包发放形式
    comment = StringField(128)  # 备注

    _indexes = ['code', 'title', 'status', 'race_cid', 'category']


class RedPacketConf(BaseModel):
    """
    红包配置
    """

    race_cid = StringField(required=True)  # 竞赛活动cid
    rule_cid = StringField(required=True)  # 红包规则cid
    category = IntegerField(required=True, choice=CATEGORY_REDPACKET_LIST)  # 红包类别（随机红包/普通红包）
    total_amount = FloatField(min_value=1.0)  # 总金额
    top_limit = IntegerField()  # 每日中奖上限
    quantity = IntegerField(min_value=1)  # 个数
    msg = StringField(max_length=64)  # 中奖提示语
    over_msg = StringField(max_length=64)  # 已达中奖上限提示语

    _indexes = ['rule_cid', 'category']


class RaceCheckPointStatistics(BaseModel):
    """
    竞赛关卡答题统计
    """

    race_cid = StringField(required=True)  # 竞赛活动cid
    member_cid = StringField(required=True)  # 会员cid
    checkpoint_stat = DictField(default={})  # 每关的答对题目数量
    correct_num = IntegerField(default=0)  # 在活动中总的答对题目数量
    pass_checkpoint_num = IntegerField(default=0)  # 通过的关卡

    _indexes = ['race_cid', 'member_cid']


class ReportSubjectStatisticsMiddle(BaseModel):
    """
    题目分析中间表
    """
    category = DictField(default=None)
    condition = DictField(default=None)
    dimension = DictField(default=None)

    code = StringField(default=None)
    custom_code = StringField(default=None)
    title = StringField(default=None)
    option_dict = DictField(default=None)
    total = IntegerField(default=0)
    correct = IntegerField(default=0)
    task_dt = DateTimeField(default=datetime.now)

    _indexes = ['category', 'condition', 'dimension', 'code', 'custom_code', 'title', 'option_dict', 'total', 'correct',
                'task_dt']


class ReportRacePeopleStatistics(BaseModel):
    """
    竞赛报表-人群统计
    """

    daily_code = StringField(default=None, required=True)
    race_cid = StringField(default=None, required=True)

    province = StringField(default=None)
    city = StringField(default=None)
    district = StringField(default=None)
    town = StringField(default=None)
    sex = IntegerField(default=None)
    education = IntegerField(default=None)
    category = IntegerField(default=None)
    company_cid = StringField(default=None)

    pass_num = IntegerField(default=0)  # 通关人数
    people_num = IntegerField(default=0)  # 当日参与人数
    # incre_people = IntegerField(default=0)  # 当日新增参与人数
    total_num = IntegerField(default=0)  # 总人次

    _indexes = ['race_cid', 'province', 'city', 'district', 'sex', 'education', 'category', 'education', 'category',
                'town', 'company_cid']


class MemberStatisticInfo(BaseModel):
    """会员中间表"""
    # 基础信息
    daily_code = StringField(required=True)  # 日期code(20190701)
    member_cid = StringField(required=True)  # 会员cid
    race_cid = StringField(required=True)  # 所属活动cid
    open_id = StringField()  # open_id
    nick_name = StringField()  # 昵称
    province = StringField()  # 省
    city = StringField()  # 市
    district = StringField()  # 区
    town = StringField()  # 乡
    company_cid = StringField(default=None)  # 公司cid
    company_name = StringField(default=None)  # 公司名
    mobile = StringField(max_length=24)  # 电话
    check_point_cid = StringField()  # 当前关cid
    check_point_index = IntegerField(default=1)  # 当前关卡号
    is_final_passed = IntegerField(default=0)  # 是否通关,是为1，不是为0
    first_time_login = DateTimeField()
    is_new_user = IntegerField(default=0)  # 是否为当日新增用户,是为1，不是为0
    # 统计信息
    answer_times = IntegerField(default=0)  # 答题数量
    true_answer_times = IntegerField(default=0)  # 答题正确数量
    draw_red_packet_count = IntegerField(default=0)  # 领取红包数
    draw_red_packet_amount = FloatField(default=0.0)  # 领取红包金额
    grant_red_packet_count = IntegerField(default=0)  # 发放红包数
    grant_red_packet_amount = FloatField(default=0.0)  # 发放红包金额
    enter_times = IntegerField(default=0)  # 每日参与次数


class RaceMemberEnterInfoStatistic(BaseModel):
    """竞赛会员参与情况中间表"""
    # 基础信息
    daily_code = StringField(required=True)  # 日期code(20190701)
    race_cid = StringField(required=True)  # 所属活动cid
    province = StringField()  # 省
    city = StringField()  # 市
    district = StringField()  # 区
    town = StringField()  # 乡
    company_cid = StringField(default=None)  # 公司cid
    company_name = StringField(default=None)  # 公司名
    increase_enter_count = IntegerField(default=0)  # 每日新增参与人数
    enter_count = IntegerField(default=0)  # 每日参与人数
    pass_count = IntegerField(default=0)  # 每日通关人数
    draw_red_packet_count = IntegerField(default=0)  # 领取红包数
    draw_red_packet_amount = FloatField(default=0.0)  # 领取红包金额
    grant_red_packet_count = IntegerField(default=0)  # 发放红包数
    grant_red_packet_amount = FloatField(default=0.0)  # 发放红包金额
    enter_times = IntegerField(default=0)  # 每日参与次数
    correct_percent = FloatField(default=0)  # 答题正确率
    answer_times = IntegerField(default=0)  # 答题数量
    true_answer_times = IntegerField(default=0)  # 答题正确数量


class AppMember(BaseModel):
    """
    app用户
    """
    code = StringField()  # 会员编号
    name = StringField()  # 会员姓名
    mobile = StringField()  # 手机号码
    nick_name = StringField()  # 昵称
    head_picture = StringField()  # 头像
    my_collection = ListField()  # 我的收藏
    my_love = ListField()  # 我的点赞
    my_recent_history = ListField()  # 我的最近浏览记录
    my_cache = ListField()  # 我的缓存列表
    is_register = IntegerField(default=0)  # 是否注册
    is_login = IntegerField(default=0)  # 是否登陆
    uuid = StringField()  # 唯一标识符
    device_id = StringField()  # 设备标识符
    device_info = DictField()  # 设备信息
    m_type = StringField()  # 头像昵称组合类型
    member_type = IntegerField(required=True, choice=MEMBER_TYPE_LIST, default=MEMBER_TYPE_NORMAL)  # 用户类型

    _indexes = ['code', 'name', 'mobile', 'is_register', 'is_login', 'member_type']


class Tvs(BaseModel):
    """
        电视剧
    """
    name = StringField()  # 电视剧名称
    dis_page_url = StringField()  # 网址链接
    db_mark = StringField()  # 豆瓣打分
    pic_url = StringField()  # 图片url
    fullname = StringField()  # 全名
    al_name = StringField()  # 又名
    area = StringField()  # 区域
    language = StringField()  # 语言
    type = ListField()  # 类型
    year = StringField()  # 年份
    screen_time = StringField()  # 上映时间&地点
    release_time = StringField()  # 发布时间
    set_num = StringField()  # 集数
    director = ListField()  # 导演
    actor = ListField()  # 主演
    label = ListField()  # 标签
    summary = StringField()  # 剧情简介
    basetitle = StringField()  # 暂时无用
    download = ListField()  # 下载bt
    status = IntegerField(choice=TV_STATUS_LIST, default=TV_STATUS_ACTIVE)  # 状态（是否有效）
    _indexes = ['name', 'area', 'language', 'year', 'director', 'actor', 'label']


class Films(BaseModel):
    """
        电影
    """
    name = StringField()  # 电影名称
    dis_page_url = StringField()  # 网址链接
    db_mark = FloatField()  # 豆瓣打分
    pic_url = StringField()  # 图片url
    fullname = StringField()  # 全名
    al_name = ListField()  # 又名
    area = StringField()  # 区域
    language = StringField()  # 语言
    type = ListField()  # 类型
    year = StringField()  # 年份
    screen_time = StringField()  # 上映时间&地点
    release_time = DateTimeField()  # 发布时间
    length = StringField()  # 片长
    director = ListField()  # 导演
    actor = ListField()  # 主演
    label = ListField()  # 标签
    summary = StringField()  # 剧情简介
    basetitle = StringField()  # 暂时无用
    download = ListField()  # 下载bt
    status = IntegerField(choice=FILM_STATUS_LIST, default=FILM_STATUS_ACTIVE)  # 状态（是否有效）
    banner_pic = StringField()  # 暂时无用
    banner_status = IntegerField(choice=FILM_STATUS_LIST, default=FILM_STATUS_INACTIVE)  # 状态（是否有效）

    _indexes = ['name', 'area', 'language', 'year', 'director', 'actor', 'label', 'status', 'banner_status', 'db_mark',
                'release_time']
