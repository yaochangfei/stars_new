# !/usr/bin/python
# -*- coding:utf-8 -*-

KEY_SESSION_USER = '_USER'  # 用户
KEY_SESSION_USER_MENU = '_USER_MENU'  # 用户菜单
KEY_SESSION_MEMBER = '_MEMBER'  # 前台登录会员

KEY_CATEGORY_VEHICLE_ATTRIBUTE_CACHE = '_CATEGORY_VEHICLE_ATTRIBUTE'  # 车型类别属性

KEY_MEMBER_CODE = '_MEMBER_CODE'  # 会员CODE
KEY_OLD_MEMBER_CACHE = 'OLD_MEMBER'
KEY_ADDRESS_CODE = '_ADDRESS_CODE'  # 地址CODE

KEY_ADMINISTRATIVE_DIVISION = '_ADMINISTRATIVE_DIVISION'  # 行政区划缓存
KEY_CODE_VEHICLE_ATTRIBUTE = '_CODE_VEHICLE_ATTRIBUTE'  # 车辆属性

# 系统自增型CODE
KEY_INCREASE_UPLOAD_FILE = '_INCREASE_UPLOAD_FILE'  # 文件自增CODE
KEY_INCREASE_USER = '_INCREASE_USER'  # 用户自增CODE
KEY_INCREASE_MEMBER_CODE = '_INCREASE_MEMBER_CODE'  # 会员自增CODE
KEY_INCREASE_QUESTIONNAIRE_CODE = '_INCREASE_QUESTIONNAIRE_CODE'  # 问卷自增CODE
KEY_INCREASE_SURVEY_ACTIVITY_CODE = '_INCREASE_SURVEY_ACTIVITY_CODE'  # 调研活动自增CODE
KEY_INCREASE_VEHICLE_CODE = '_INCREASE_VEHICLE_CODE'  # 车型自增CODE
KEY_INCREASE_PRESENT_CODE = '_INCREASE_PRESENT_CODE'  # 礼品自增CODE
KEY_INCREASE_SUBJECT_CODE = '_INCREASE_SUBJECT_CODE'  # 题目自增CODE
KEY_INCREASE_SUBJECT_OPTION_CODE = '_INCREASE_SUBJECT_OPTION_CODE'  # 题目选项自增CODE
KEY_INCREASE_EXCHANGE_ORDER_CODE = '_INCREASE_EXCHANGE_ORDER_CODE'  # 订单code key

KEY_CACHE_SUBJECT_RESULT = 'CACHE_SUBJECT_RESULT'  # 答题结果缓存

KEY_ANSWER_LIMIT = '_ANSWER_LIMIT'  # 答题限制

KEY_PREFIX_TASK_DOCKING_STATISTICS = '_PREFIX_TASK_DOCKING_STATISTICS'  # 对接统计队列标记
KEY_ALLOW_PROCESS_DOCKING_STATISTICS = '_ALLOW_PROCESS_DOCKING_STATISTICS'  # 标记后台任务是否可以处理对接数据

KEY_PREFIX_TASK_ACCURATE_STATISTICS = '_PREFIX_TASK_ACCURATE_STATISTICS'  # 系统精确统计队列标记
KEY_ALLOW_PROCESS_ACCURATE_STATISTICS = '_ALLOW_PROCESS_ACCURATE_STATISTICS'  # 标记后台任务是否可以处理正确率数据

KEY_CACHE_MEMBER_SHARE_TIMES = '_CACHE_MEMBER_SHARE_TIMES'  # 分享次数缓存

KEY_EXTRACTING_SUBJECT_RULE = '_EXTRACTING_SUBJECT_RULE'  # 抽题规则
KEY_PREFIX_EXTRACTING_SUBJECT_RULE = '_PREFIX_EXTRACTING_SUBJECT_RULE'  # 抽题规则执行状态
KEY_EXTRACTING_SUBJECT_QUANTITY = '_EXTRACTING_SUBJECT_QUANTITY'  # 抽题规则题目组数量

KEY_PREFIX_TASK_ROBOT_ANALYSIS_REFERENCE = '_PREFIX_TASK_ROBOT_ANALYSIS_REFERENCE'  # 系统精确统计队列标记
KEY_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE = '_ALLOW_PROCESS_ROBOT_ANALYSIS_REFERENCE'  # 标记后台任务是否可以处理正确率数据

KEY_PREFIX_TASK_REPORT_DATA_STATISTICS = '_PREFIX_TASK_REPORT_DATA_STATISTICS'  # 报表数据统计队列标记
KEY_ALLOW_TASK_MEMBER_DAILY_STATISTICS = '_ALLOW_TASK_MEMBER_DAILY_STATISTICS'  # 标记后台任务是否可以处理会员每日统计
KEY_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS = '_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS'  # 标记后台任务是否可以处理会员题目统计
KEY_ALLOW_TASK_MEMBER_DIMENSION_STATISTICS = '_ALLOW_TASK_MEMBER_SUBJECT_STATISTICS'  # 标记后台任务是否可以处理维度统计
KEY_ALLOW_TASK_MEMBER_LEARNING_DAYS_STATISTICS = '_ALLOW_TASK_MEMBER_LEARNING_DAYS_STATISTICS'  # 标记后台任务是否可以处理会员学习日统计
KEY_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS = '_ALLOW_TASK_MEMBER_DAILY_DIMENSION_STATISTICS'  # 标记后台任务是否可以处理会员每日维度统计
KEY_ALLOW_TASK_MEMBER_LEARNING_DAY_DIMENSION_STATISTICS = '_ALLOW_TASK_MEMBER_LEARNING_DAY_DIMENSION_STATISTICS'  # 标记后台任务是否可以处理会员每学习日维度统计

KEY_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS = '_ALLOW_TASK_NEW_MEMBER_PROPERTY_STATISTICS'  # 标记后台任务是否可以处理新会员统计

KEY_PREFIX_SUBJECT_BANKS_COUNT = '_PREFIX_SUBJECT_BANKS_COUNT'  # 题库数量标记
KEY_PREFIX_DAN_GRADE_LIST = '_PREFIX_DAN_GRADE_LIST' # 段位列表

KEY_CACHE_RACE_COPY_MAP = '_CACHE_RACE_COPY_SUBJECT_MAP'  # 活动复制时新旧题库映射的缓存
KEY_RACE_LOTTERY_QUEUING = 'CRSPN_RACE_LOTTERY_QUEUING_{0}'  # 竞赛活动抽奖排队
KEY_RACE_LOTTERY_in_PROCESS = 'CRSPN_RACE_LOTTERY_in_PROCESS_{0}'  #  抽奖中
KEY_RACE_LOTTERY_RESULT = 'CRSPN_RACE_LOTTERY_RESULT_{0}'  # 竞赛活动抽奖结果

KEY_CACHE_REPORT_CONDITION = '_CACHE_REPORT_CONDITION'  # 题目分析条件缓存
KEY_CACHE_REPORT_DOING_NOW = '_CACHE_REPORT_DOING_NOW'  # 报表数据处理中
KEY_CACHE_REPORT_ECHARTS_CONDITION = '_CACHE_REPORT_ECHARTS_CONDITION'  # 图表条件缓存

KEY_CACHE_WECHAT_AD_DIVISION = '_CACHE_WECHAT_AD_DIVISION'  # 小程序行政区划缓存
KEY_CACHE_RACE_REPORT_DOWNLOAD = '_CACHE_RACE_REPORT'  # 科协导出数据缓存
KEY_CACHE_APPLET_ONLINE_MEMBER = '_CACHE_ONLINE_MEMBER'  # 小程序在线人数缓存
KEY_CACHE_LOTTERY_TABLE = '_CACHE_LOTTERY_TABLE'  # 获取抽奖转盘

KEY_CACHE_WECHAT_TOWN = '_CACHE_WECHAT_TOWN'  # 小程序乡镇信息缓存

# 学习效果图表配色
CHART_COLOR_LIST = ['#A0D368', '#F7A34F', '#8085E9', '#F15C80', '#297A47', '#81D5AF', '#B3D581', '#214D63', '#BF4044', '#736126']
