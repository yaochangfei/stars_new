# !/usr/bin/python
# -*- coding:utf-8 -*-
import datetime
import json
import mimetypes
import os
import random
import time
import uuid

import requests
from caches.redis_utils import RedisCache
from commons.common_utils import read_json_resource, datetime2timestamp, get_file_extension_name, sha1, string, \
    datetime2str, md5
from db import STATUS_SUBJECT_ACTIVE, TYPE_DAN_GRADE_ONE, CODE_SUBJECT_DIFFICULTY_SIMPLE, TYPE_DAN_GRADE_TWO, \
    TYPE_DAN_GRADE_THIRD, CODE_SUBJECT_DIFFICULTY_MEDIUM, TYPE_DAN_GRADE_FOUR, TYPE_DAN_GRADE_SIX, TYPE_DAN_GRADE_FIVE, \
    CODE_SUBJECT_DIFFICULTY_HIGH, TYPE_DAN_GRADE_SEVEN, TYPE_DAN_GRADE_EIGHT, TYPE_DAN_GRADE_NINE, TYPE_DAN_GRADE_TEN, \
    TYPE_DAN_GRADE_ELEVEN, CATEGORY_SUBJECT_KNOWLEDGE_DICT, TYPE_STAR_GRADE_ZERO, STATUS_RESULT_GAME_PK_WIN, \
    STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP, STATUS_RESULT_GAME_PK_TIE_BREAK, TYPE_DAN_GRADE_LIST, \
    DAN_STAR_GRADE_MAPPING, TYPE_STAR_GRADE_ONE, SOURCE_MEMBER_DIAMOND_FIRST_PK, \
    SOURCE_MEMBER_INTEGRAL_FIRST_KNOWLEDGE_PK, SOURCE_MEMBER_INTEGRAL_KNOWLEDGE_PK_EVERYDAY, \
    SOURCE_MEMBER_DIAMOND_FIRST_WIN, SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES, \
    SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND, \
    SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, SOURCE_MEMBER_DIAMOND_PK_VICTORY, SOURCE_MEMBER_INTEGRAL_LIST, \
    SOURCE_MEMBER_INTEGRAL_DICT, SOURCE_MEMBER_DIAMOND_LIST, SOURCE_MEMBER_DIAMOND_DICT, KNOWLEDGE_FIRST_LEVEL_DICT, \
    KNOWLEDGE_SECOND_LEVEL_DICT, TYPE_DAN_GRADE_DICT, STATUS_USER_ACTIVE, \
    SOURCE_MEMBER_DIAMOND_DAILY_RANKING, SOURCE_MEMBER_DIAMOND_DAILY_RANKING_VALUE_LIMIT, \
    CODE_SUBJECT_DIFFICULTY_FORTH, CODE_SUBJECT_DIFFICULTY_FIFTH, STATUS_WRONG_SUBJECT_INACTIVE, \
    CODE_SUBJECT_DIFFICULTY_LIST, STATUS_GAME_CHECK_POINT_ACTIVE, STATUS_RESULT_CHECK_POINT_WIN
from db.enums import CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION
from db.models import Subject, MemberGameHistory, GameDiamondConsume, GameDiamondReward, SubjectOption, Member, \
    MemberIntegralSource, MemberIntegralDetail, MemberDiamondDetail, UploadFiles, MemberWrongSubject, \
    MemberCheckPointHistory, RaceGameCheckPoint, RaceMapping, RaceCheckPointStatistics, ReportRacePeopleStatistics
from enums import KEY_CACHE_SUBJECT_RESULT
from logger import log_utils
from motorengine import DESC, ASC
from motorengine.stages import MatchStage, SampleStage, SortStage, LookupStage, LimitStage
from motorengine.stages.project_stage import ProjectStage
from pymongo import ReadPreference
from settings import TOKEN, APP_ID, APP_SECRET, SERVER_HOST, SERVER_PROTOCOL, STATIC_URL_PREFIX
from tasks.instances.task_accurate_statistics import start_accurate_statistics
from tasks.instances.task_report_dashboard_statistics import start_dashboard_report_statistics
from tasks.instances.task_robot_analysis_reference import task_robot_analysis_reference_statistics
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from wechat import KEY_WECHAT_ACCESS_TOKEN_CACHE, API_ACCESS_TOKEN_URL, API_MENU_CREATE_URL, EVENT_WECHAT_SUBSCRIBE, \
    EVENT_WECHAT_LOCATION, KEY_WECHAT_MENU_SURVEY_LATEST, EVENT_WECHAT_LATEST_SURVEY, KEY_WECHAT_MENU_SIGN_IN, \
    EVENT_WECHAT_SIGN_IN, API_CODE_EXCHANGE_ACCESS_TOKEN_URL, TEMPLATE_TXT_PASSIVE, API_PUSH_PIC_TXT_MESSAGE_URL, \
    API_PIC_TXT_MATERIAL_UPLOAD_URL, API_MEDIA_UPLOAD_URL, API_PUSH_TEMPLATE_MESSAGE_URL, MINI_APP_STATIC_URL_PREFIX
from wechat.templates import TEMPLATE_ARTICLE_PIC_TXT_PASSIVE, TEMPLATE_PIC_TXT_PASSIVE

requests.packages.urllib3.disable_warnings()

logger = log_utils.get_logging()


def check_signature(request_handler):
    """
    检查微信服务器请求签名
    :param request_handler: 请求句柄
    :return:
    """
    if request_handler:
        signature = request_handler.get_argument('signature', None)
        timestamp = request_handler.get_argument('timestamp', None)
        nonce = request_handler.get_argument('nonce', None)
        echostr = request_handler.get_argument('echostr', None)

        if signature and timestamp and nonce:
            signature_arr = sorted([TOKEN, timestamp, nonce])
            signature_str = "%s%s%s" % tuple(signature_arr)
            if sha1(signature_str) == signature:
                return True, echostr
    return False, None


def get_access_token(refresh=False):
    """
    获取Access Token
    :param refresh: 强制刷新
    :return:
    """
    if not refresh:
        access_token = RedisCache.get(KEY_WECHAT_ACCESS_TOKEN_CACHE)
        if access_token:
            return access_token
    response = requests.get(API_ACCESS_TOKEN_URL, verify=False)
    if response.status_code == 200:
        rep_dict = json.loads(response.text)
        errcode = rep_dict.get('errcode')
        if errcode:
            logger.error('Get wechat Access Token failed, errcode=%s.' % errcode)
            raise ValueError('Get wechat Access Token failed, errcode=%s.' % errcode)
        else:
            access_token = rep_dict.get('access_token')
            if access_token:
                RedisCache.set(KEY_WECHAT_ACCESS_TOKEN_CACHE, access_token, 7200)
                return access_token
            else:
                logger.error('Get wechat Access Token failed.')
                raise ValueError('Get wechat Access Token failed.')
    else:
        logger.error('Get wechat Access Token failed.')
        raise ValueError('Get wechat Access Token failed.')


def do_generate_menu():
    """
    生成微信菜单
    :return:
    """
    menu_json = json.dumps(read_json_resource('wechat_menu.json'), ensure_ascii=False).encode('utf-8')
    access_token = get_access_token()
    menu_create_api = API_MENU_CREATE_URL % access_token
    response = requests.post(menu_create_api, data=menu_json, verify=False)
    response_json = json.loads(response.text)
    if response_json.get('errcode') == 0:
        return True
    else:
        logger.error(str(response_json))
    return False


def get_open_id(req_body_dict):
    """
    从请求结果里获取open_id
    :param req_body_dict:
    :return:
    """
    if req_body_dict:
        open_id = req_body_dict.get('FromUserName')
        if open_id:
            return string(open_id)
    return None


def get_service_id(req_body_dict):
    """
    从请求结果里获取service_id
    :param req_body_dict:
    :return:
    """
    if req_body_dict:
        service_id = req_body_dict.get('ToUserName')
        if service_id:
            return string(service_id)
    return None


def get_event_type(req_body_dict):
    if req_body_dict:
        msg_type = string(req_body_dict.get('MsgType')).upper()
        if msg_type == 'EVENT':
            event = string(req_body_dict.get('Event')).upper()
            if event == 'SUBSCRIBE':
                return EVENT_WECHAT_SUBSCRIBE
            elif event == 'LOCATION':
                return EVENT_WECHAT_LOCATION
            elif event == 'CLICK':
                event_key = string(req_body_dict.get('EventKey')).upper()
                if event_key == KEY_WECHAT_MENU_SURVEY_LATEST:
                    return EVENT_WECHAT_LATEST_SURVEY
                elif event_key == KEY_WECHAT_MENU_SIGN_IN:
                    return EVENT_WECHAT_SIGN_IN
    return None


async def get_oauth20_openid(auth_code):
    """
    获取网页授权OpenID
    :param auth_code: 网页授权的CODE
    :return: 用户OpenID
    """
    open_id = None
    if auth_code:
        exchange_url = API_CODE_EXCHANGE_ACCESS_TOKEN_URL % (APP_ID, APP_SECRET, auth_code)
        http_client = AsyncHTTPClient()
        response = await http_client.fetch(exchange_url)
        if response.code == 200:
            rep_dict = json.loads(response.body.decode('utf-8'))
            open_id = rep_dict.get('openid')
            if not open_id:
                error_code = rep_dict.get('errcode')
                if error_code:
                    logger.error('%s(%s)' % (rep_dict['errmsg'], error_code))
    return open_id


def get_new_msg_id():
    """
    获取一个全新的消息ID
    :return:
    """
    return str(time.time()).replace('.', '')


def get_a_passive_txt_message(open_id, service_id, content):
    """
    获取被动回复文本消息
    :param open_id: 接受者OpenID
    :param service_id: 开发者微信号
    :param content: 消息内容
    :return:
    """
    if open_id and service_id and content:
        args_dict = {
            'open_id': open_id,
            'service_id': service_id,
            'timestamp': datetime2timestamp(datetime.datetime.now()),
            'content': content,
            'msg_id': get_new_msg_id()
        }
        return TEMPLATE_TXT_PASSIVE.format(**args_dict)
    return None


def get_a_passive_pt_message(open_id, service_id, article_dict_list):
    """
    获取被动回复图文消息
    :param open_id: 接受者OpenID
    :param service_id: 开发者微信号
    :param article_dict_list: 消息内容
    :return:
    """
    if open_id and service_id and article_dict_list:
        if len(article_dict_list) > 8:
            raise ValueError('article_dict_list\'s max length is 8.')
        articles_xml = ''
        for article_dict in article_dict_list:
            if isinstance(article_dict, dict):
                if 'title' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "title".')
                if 'description' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "description".')
                if 'pic_url' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "pic_url".')
                if 'url' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "url".')
            else:
                raise ValueError('article_dict_list\'s content can only be dicts.')

            articles_xml += TEMPLATE_ARTICLE_PIC_TXT_PASSIVE.format(**article_dict)
        if articles_xml:
            args_dict = {
                'open_id': open_id,
                'service_id': service_id,
                'timestamp': datetime2timestamp(datetime.datetime.now()),
                'article_count': len(article_dict_list),
                'articles': articles_xml
            }
            return TEMPLATE_PIC_TXT_PASSIVE.format(**args_dict)
    return ''


def push_active_txt_message(open_id_list, msg_content):
    """
    主动推送文本消息
    :param open_id_list:
    :param msg_content:
    :return:
    """
    if open_id_list and msg_content:
        data = {
            "touser": [open_id_list],
            "msgtype": "text",
            "text": {
                "content": msg_content
            }
        }
        response = requests.post(API_PUSH_PIC_TXT_MESSAGE_URL % get_access_token(), data=data)
        if response.status_code == 200:
            rep_dict = json.loads(response.text)
            return rep_dict
    return {}


def push_active_pt_message(open_id_list, msg_list):
    """
    主动推送图文消息
    msg_list = [{
            "cover": "/Users/samuel.zhang/Pictures/Wallpapers/cover.jpg",
            "author": "xxx",
            "title": "Happy Day",
            "content_source_url": "www.idiaoyan.com",
            "content": "content",
            "digest": "digest",
            "show_cover_pic": 1
        }, {
            "cover": "/Users/samuel.zhang/Pictures/Wallpapers/cover.jpg",
            "author": "xxx",
            "title": "Happy Day",
            "content_source_url": "www.idiaoyan.com",
            "content": "content",
            "digest": "digest",
            "show_cover_pic": 0
        }]
    :param open_id_list:
    :param msg_list:
    :return:
    """
    if open_id_list and msg_list:
        article_dict_list = []
        for msg in msg_list:
            if isinstance(msg, dict):
                if 'cover' not in msg.keys():
                    raise ValueError('"msg" in msg_list has no key "cover".')
                if 'title' not in msg.keys():
                    raise ValueError('"msg" in msg_list has no key "title".')
                if 'content' not in msg.keys():
                    raise ValueError('"msg" in msg_list has no key "content".')
            else:
                raise ValueError('content_list\'s content can only be dicts.')
            media_dict = upload_pic_txt_image(msg.get('cover'))
            if media_dict:
                media_id = media_dict.get('media_id')
                if media_id:
                    article_dict = {'thumb_media_id': media_id, 'title': msg.get('title'),
                                    'content': msg.get('content')}
                    if msg.get('author'):
                        article_dict['author'] = msg.get('author')
                    if msg.get('content_source_url'):
                        article_dict['content_source_url'] = msg.get('content_source_url')
                    if msg.get('digest'):
                        article_dict['digest'] = msg.get('digest')
                    if msg.get('show_cover_pic'):
                        article_dict['show_cover_pic'] = msg.get('show_cover_pic')
                    article_dict_list.append(article_dict)
        if article_dict_list:
            material_dict = upload_pic_txt_material(article_dict_list)
            if material_dict:
                media_id = material_dict.get('media_id')
                if media_id:
                    data = {
                        "touser": open_id_list,
                        "mpnews": {
                            "media_id": media_id
                        },
                        "msgtype": "mpnews",
                        "send_ignore_reprint": 1
                    }
                    response = requests.post(API_PUSH_PIC_TXT_MESSAGE_URL % get_access_token(), data=data)
                    if response.status_code == 200:
                        rep_dict = json.loads(response.text)
                        return rep_dict
    return {}


def upload_pic_txt_material(article_dict_list):
    """
    上传图文消息素材
    :param article_dict_list:
    :return:
    """
    if article_dict_list:
        articles = []
        for article_dict in article_dict_list:
            if article_dict:
                if 'thumb_media_id' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "thumb_media_id".')
                if 'title' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "title".')
                if 'content' not in article_dict.keys():
                    raise ValueError('"article" in article_dict_list has no key "content".')
                article = {
                    'thumb_media_id': article_dict.get('thumb_media_id'),
                    'title': article_dict.get('title'),
                    'content': article_dict.get('content')
                }
                if article_dict.get('author'):
                    article['author'] = article_dict.get('author')
                if article_dict.get('content_source_url'):
                    article['content_source_url'] = article_dict.get('content_source_url')
                if article_dict.get('digest'):
                    article['digest'] = article_dict.get('digest')
                if article_dict.get('show_cover_pic'):
                    article['show_cover_pic'] = article_dict.get('show_cover_pic')
                articles.append(articles)
        if articles:
            response = requests.post(API_PIC_TXT_MATERIAL_UPLOAD_URL % get_access_token(), data=articles, verify=False)
            if response.status_code == 200:
                rep_dict = json.loads(response.text)
                return rep_dict
    return {}


def upload_pic_txt_image(file_path):
    """
    上传多媒体文件（阻塞的）
    :param file_path: 问卷绝对路径
    :return:
    """
    if file_path:
        args_dict = {'access_token': get_access_token(), 'media_type': 'image'}
        files_dict = {'file': open(file_path, 'rb')}
        response = requests.post(API_MEDIA_UPLOAD_URL.format(**args_dict), files=files_dict, verify=False)
        if response.status_code == 200:
            rep_dict = json.loads(response.text)
            return rep_dict
    return {}


async def upload_pt_image_no_blocking(file_path):
    """
    上传多媒体文件（无阻塞的）
    :param file_path: 问卷绝对路径
    :return:
    """
    content_type, body = _encode_multipart_data(file_path)
    headers = {"Content-Type": content_type, 'content-length': str(len(body))}
    args_dict = {'access_token': get_access_token(), 'media_type': 'image'}
    request = HTTPRequest(API_MEDIA_UPLOAD_URL.format(**args_dict), method="POST", headers=headers, body=body,
                          validate_cert=False)
    response = await AsyncHTTPClient().fetch(request)
    if response.code == 200:
        rep_dict = json.loads(response.body)
        return rep_dict
    return {}


def _encode_multipart_data(file_path):
    """
    编码附件请求
    :param file_path: 附件绝对路径
    :return:
    """
    if os.path.exists(file_path):
        with open(file_path, 'rb') as f:
            filename = ('%s%s' % (uuid.uuid1().hex, get_file_extension_name(f.name))).encode("utf8")
            boundary = uuid.uuid1().hex
            content_list = [
                '--' + boundary,
                'Content-Disposition: form-data; name="image"; filename="%s"' % filename,
                'Content-Type: %s' % mimetypes.guess_type(filename)[0] or 'application/octet-stream',
                '',
                f.read(),
                '--' + boundary + '--',
                ''
            ]
            content_type = 'multipart/form-data; boundary=%s' % boundary
            body = '\r\n'.join(content_list)
            return content_type, body
    return None, None


def push_active_template_message(template_id, open_id, content_data, to_url=None):
    """
    推送模板消息
        content_data = {
            'head': {
                'value': 'value',
                'color': '#173177'
            },
            'title': {
                'value': 'title',
                'color': '#000000'
            }
        }
    :param template_id: 模板编号
    :param open_id: 微信OpenID
    :param content_data: 消息内容
    :param to_url L模板跳转链接
    :return:
    """
    if template_id and open_id and content_data:
        post_data = {
            'touser': open_id,
            'template_id': template_id,
            'data': content_data
        }
        if to_url:
            post_data['url'] = to_url
        post_data = json.dumps(post_data, ensure_ascii=False).encode('utf-8')
        response = requests.post(API_PUSH_TEMPLATE_MESSAGE_URL % get_access_token(), data=post_data, verify=False)
        if response.status_code == 200:
            rep_dict = json.loads(response.text)
            return rep_dict
    return {}


async def get_pk_questions(grade):
    """
    根据段位规则抓取题目数据
    入门新手：简单5
    坚定磐石：简单4，中等1
    无畏黑铁：简单3，中等2
    勇敢青铜：简单2，中等3
    秩序白银：简单1，中等4
    高贵黄金：简单1，中等3，困难1
    庄严白金：中等4，困难1
    奢华铂金：中等3，困难2
    光辉钻石：中等2，困难3
    一代宗师：困难1，困难4
    车界传说：困难5
    :param grade:
    :return:
    """

    question_cid_list = []
    filter_dict = {
        'status': STATUS_SUBJECT_ACTIVE,
        'record_flag': 1,
        'category_use': {'$ne': {'$in': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}},
    }

    if grade == TYPE_DAN_GRADE_ONE:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 5)]
    elif grade == TYPE_DAN_GRADE_TWO:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 4),
                                  (CODE_SUBJECT_DIFFICULTY_MEDIUM, 1)]
    elif grade == TYPE_DAN_GRADE_THIRD:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 3),
                                  (CODE_SUBJECT_DIFFICULTY_MEDIUM, 2)]
    elif grade == TYPE_DAN_GRADE_FOUR:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 2),
                                  (CODE_SUBJECT_DIFFICULTY_MEDIUM, 3)]
    elif grade == TYPE_DAN_GRADE_FIVE:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 1),
                                  (CODE_SUBJECT_DIFFICULTY_MEDIUM, 3),
                                  (CODE_SUBJECT_DIFFICULTY_HIGH, 1)]
    elif grade == TYPE_DAN_GRADE_SIX:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_SIMPLE, 1),
                                  (CODE_SUBJECT_DIFFICULTY_MEDIUM, 2),
                                  (CODE_SUBJECT_DIFFICULTY_HIGH, 1),
                                  (CODE_SUBJECT_DIFFICULTY_FORTH, 1)]
    elif grade == TYPE_DAN_GRADE_SEVEN:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_MEDIUM, 1),
                                  (CODE_SUBJECT_DIFFICULTY_HIGH, 2),
                                  (CODE_SUBJECT_DIFFICULTY_FORTH, 1),
                                  (CODE_SUBJECT_DIFFICULTY_FIFTH, 1)]
    elif grade == TYPE_DAN_GRADE_EIGHT:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_MEDIUM, 1),
                                  (CODE_SUBJECT_DIFFICULTY_HIGH, 1),
                                  (CODE_SUBJECT_DIFFICULTY_FORTH, 2),
                                  (CODE_SUBJECT_DIFFICULTY_FIFTH, 1)]
    elif grade == TYPE_DAN_GRADE_NINE:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_HIGH, 1),
                                  (CODE_SUBJECT_DIFFICULTY_FORTH, 2),
                                  (CODE_SUBJECT_DIFFICULTY_FIFTH, 2)]
    elif grade == TYPE_DAN_GRADE_TEN:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_FORTH, 1),
                                  (CODE_SUBJECT_DIFFICULTY_FIFTH, 4)]
    elif grade == TYPE_DAN_GRADE_ELEVEN:
        difficulty_sample_list = [(CODE_SUBJECT_DIFFICULTY_FIFTH, 5)]
    else:
        difficulty_sample_list = []

    res_list = await get_temp_questions(filter_dict, difficulty_sample_list)
    question_cid_list.extend(res_list)

    return question_cid_list


async def get_temp_questions(filter_dict, difficulty_sample_list):
    res_list = []

    for difficulty, sample in difficulty_sample_list:
        filter_dict['difficulty'] = difficulty

        temp_list = await Subject.aggregate(
            [
                MatchStage(filter_dict),
                SampleStage(sample),
                ProjectStage(id=False, cid=True),
                SortStage([('code', DESC)])
            ]).to_list(None)
        res_list.extend(temp_list)

    return res_list


async def deal_questions(question_cid_list):
    """
    根据题目code处理数据
    :param question_cid_list:
    :return:
    """
    question_list = []
    is_current = True
    for question_cid in question_cid_list:
        subject_list = await Subject.aggregate(
            [
                MatchStage(dict(cid=question_cid)),
                LookupStage(SubjectOption, 'cid', 'subject_cid', 'option_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')
            ]
        ).to_list(1)

        if subject_list:
            subject = subject_list[0]
            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''
            difficulty = subject.difficulty
            difficulty_list = []
            for i in range(1, 6):
                if difficulty >= i:
                    temp_difficulty = {
                        'show': 'star_degree'
                    }
                else:
                    temp_difficulty = {
                        'show': ''
                    }
                difficulty_list.append(temp_difficulty)

            question = {
                'id': subject.cid,
                'title': subject.title,
                'title_picture_url': title_picture_url,
                'subject_type': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category),
                'is_current': is_current,
                'total_time': 20,
                'difficulty_list': difficulty_list,
                'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
                'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
                'resolving': subject.resolving
            }

            is_current = False

            option_doc_list = subject.option_list if subject.option_list else []
            option_list = []
            for option_doc in option_doc_list:
                option = {
                    'title': option_doc.title,
                    'id': option_doc.cid,
                    'true_answer': option_doc.correct,
                    'option_show': ''
                }
                option_list.append(option)

            question['options'] = option_list
            question_list.append(question)

    return question_list


async def get_level_list_info(member, pk_status=None, unlock=None, pk_grade=None):
    """
    根据当前段位获取段位列表信息
    win=NOne, unlock=None 为正常状态
    win=True, unlock=True 为解锁下一段位
    unlock=False 为未解锁
    :param member:
    :param unlock:
    :param pk_status:
    :param pk_grade:
    :return:
    """
    # 当前段位
    current_level = member.dan_grade
    if current_level is None:
        current_level = TYPE_DAN_GRADE_ONE
    # 当前段位星级
    current_star = member.star_grade
    if current_star is None:
        current_star = TYPE_STAR_GRADE_ZERO
    # 段位消耗积分对应关系
    filter_dict = {
        'record_flag': 1,
        'source': {
            '$ne': None,
            '$lte': current_level + 2
        },
    }
    diamond_consume_list = await GameDiamondConsume.find(filter_dict).sort([('source', ASC)]).to_list(
        current_level + 2)

    diamond_consume_dict = {diamond_consume.source: diamond_consume.quantity for diamond_consume in
                            diamond_consume_list}
    if pk_status is None and unlock is None:
        level_list = get_common_level_list(current_level, current_star, diamond_consume_dict)
        level_list_new = []
    elif pk_status is not None and unlock is not None:
        # 判断用户段位和答题段位是否一致
        if pk_grade is not None and pk_grade == current_level:
            if pk_status == STATUS_RESULT_GAME_PK_WIN:
                if unlock:
                    # 初始动画
                    level_list = get_dynamic_level_list(current_level, current_star, True, False, diamond_consume_dict)
                    # 解锁动画
                    level_list_new = get_dynamic_level_list(current_level, current_star, True, unlock,
                                                            diamond_consume_dict)
                else:
                    # 初始动画
                    level_list = get_dynamic_level_list(current_level, current_star, True, unlock, diamond_consume_dict)
                    level_list_new = []
            elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
                level_list = get_common_level_list(current_level, current_star, diamond_consume_dict)
                level_list_new = []
            elif pk_status in [STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP]:
                level_list = get_dynamic_level_list(current_level, current_star, False, False, diamond_consume_dict)
                level_list_new = []
            else:
                level_list = []
                level_list_new = []
        else:
            level_list = get_common_level_list(current_level, current_star, diamond_consume_dict)
            level_list_new = []
    else:
        level_list = []
        level_list_new = []
    return level_list, level_list_new


async def get_level_list_info2(member, pk_status=None, unlock=None, pk_grade=None):
    """
    根据当前段位获取段位列表信息
    win=NOne, unlock=None 为正常状态
    win=True, unlock=True 为解锁下一段位
    unlock=False 为未解锁
    :param member:
    :param unlock:
    :param pk_status:
    :param pk_grade:
    :return:
    """
    # 当前段位
    current_level = member.dan_grade
    if current_level is None:
        current_level = TYPE_DAN_GRADE_ONE
    # 当前段位星级
    current_star = member.star_grade
    if current_star is None:
        current_star = TYPE_STAR_GRADE_ZERO
    # 段位消耗积分对应关系
    filter_dict = {
        'record_flag': 1,
        'source': {
            '$ne': None,
        },
    }
    diamond_consume_list = await GameDiamondConsume.find(filter_dict).sort([('source', ASC)]).to_list(None)

    diamond_consume_dict = {diamond_consume.source: diamond_consume.quantity for diamond_consume in
                            diamond_consume_list}
    if pk_status is None and unlock is None:
        level_list = get_common_level_list2(current_level, current_star, diamond_consume_dict)
        level_list_new = []
    elif pk_status is not None and unlock is not None:
        # 判断用户段位和答题段位是否一致
        if pk_grade is not None and pk_grade == current_level:
            if pk_status == STATUS_RESULT_GAME_PK_WIN:
                if unlock:
                    # 初始动画
                    level_list = get_dynamic_level_list2(current_level, current_star, True, False, diamond_consume_dict)
                    # 解锁动画
                    level_list_new = get_dynamic_level_list2(current_level, current_star, True, unlock,
                                                             diamond_consume_dict)
                else:
                    # 初始动画
                    level_list = get_dynamic_level_list2(current_level, current_star, True, unlock,
                                                         diamond_consume_dict)
                    level_list_new = []
            elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
                level_list = get_common_level_list2(current_level, current_star, diamond_consume_dict)
                level_list_new = []
            elif pk_status in [STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP]:
                level_list = get_dynamic_level_list2(current_level, current_star, False, False, diamond_consume_dict)
                level_list_new = []
            else:
                level_list = []
                level_list_new = []
        else:
            level_list = get_common_level_list2(current_level, current_star, diamond_consume_dict)
            level_list_new = []
    else:
        level_list = []
        level_list_new = []
    return level_list, level_list_new


def get_common_level_list2(current_level, current_star, diamond_consume_dict):
    """
    获取默认的列表数据
    :param current_level:
    :param current_star:
    :param diamond_consume_dict:
    :return:
    """
    level_list = []

    # 默认显示下一级
    for grade_code in TYPE_DAN_GRADE_LIST:

        # name 地址
        name = '{protocol}://{host}{static_url}level{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)
        title = TYPE_DAN_GRADE_DICT.get(grade_code)

        # logo 地址
        logo = '{protocol}://{host}{static_url}sign{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)

        # 钻石消耗
        diamond_consume = diamond_consume_dict.get(grade_code, 0)

        # 是否锁
        if grade_code > current_level:
            if_lock = 1
        else:
            if_lock = 0

        # stars
        # 下一级锁定
        if grade_code > current_level:
            stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        elif grade_code < current_level:
            stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        elif grade_code == current_level:

            # 判断最后一级全部解锁
            if grade_code == TYPE_DAN_GRADE_ELEVEN and current_star == DAN_STAR_GRADE_MAPPING.get(grade_code):
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            else:

                stars = []
                for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code) - current_star):
                    stars.append({'status': ''})

                for _ in range(current_star):
                    stars.append({'status': 'through'})

        else:
            stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]

        level_dict = {
            'id': grade_code,
            'name': name,
            'logo': logo,
            'if_lock': if_lock,
            'stars': stars,
            'cost': diamond_consume,
            'title': title
        }

        level_list.append(level_dict)

    return level_list


def get_common_level_list(current_level, current_star, diamond_consume_dict):
    """
    获取默认的列表数据
    :param current_level:
    :param current_star:
    :param diamond_consume_dict:
    :return:
    """
    level_list = []

    # 默认显示下一级
    for grade_code in TYPE_DAN_GRADE_LIST[:current_level + 1]:

        # name 地址
        name = '{protocol}://{host}{static_url}level{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)
        title = TYPE_DAN_GRADE_DICT.get(grade_code)

        # logo 地址
        logo = '{protocol}://{host}{static_url}sign{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)

        # 钻石消耗
        diamond_consume = diamond_consume_dict.get(grade_code, 0)

        # 是否锁
        if grade_code == current_level + 1:
            if_lock = 1
        else:
            if_lock = 0

        # stars
        # 下一级锁定
        if grade_code == current_level + 1:
            stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        elif grade_code < current_level:
            stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        elif grade_code == current_level:

            # 判断最后一级全部解锁
            if grade_code == TYPE_DAN_GRADE_ELEVEN and current_star == DAN_STAR_GRADE_MAPPING.get(grade_code):
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            else:

                stars = []
                for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code) - current_star):
                    stars.append({'status': ''})

                for _ in range(current_star):
                    stars.append({'status': 'through'})

        else:
            stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]

        level_dict = {
            'id': grade_code,
            'name': name,
            'logo': logo,
            'if_lock': if_lock,
            'stars': stars,
            'cost': diamond_consume,
            'title': title
        }

        level_list.append(level_dict)

    return level_list


def get_dynamic_level_list(current_level, current_star, win, unlock, diamond_consume_dict):
    """
    答题完成后的列表数据
    有相对应的css
    :param current_level:
    :param current_star:
    :param win:
    :param unlock:
    :param diamond_consume_dict:
    :return:
    """
    level_list = []

    # 默认显示下一级
    for grade_code in TYPE_DAN_GRADE_LIST[:current_level + 1 if not unlock else current_level + 2]:

        # name 地址
        name = '{protocol}://{host}{static_url}level{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)
        title = TYPE_DAN_GRADE_DICT.get(grade_code)
        # logo 地址
        logo = '{protocol}://{host}{static_url}sign{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)

        # 钻石消耗
        diamond_consume = diamond_consume_dict.get(grade_code, 0)

        # 是否锁
        if grade_code <= current_level:
            # 当前的答题段位大于该段位
            if_lock = 0
        else:
            if not unlock and grade_code == current_level + 1:
                # 没有解锁下一段位
                # 且该段位 等于 当前答题段位 + 1
                if_lock = 1
            elif unlock and grade_code == current_level + 2:
                # 解锁下一段位
                # 且该段位 等于 当前答题段位 + 2
                if_lock = 1
            else:
                if_lock = 0

        # stars
        if not unlock:

            if grade_code == current_level + 1:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code < current_level:
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code == current_level:

                stars = []
                if win:
                    range_empty_star = DAN_STAR_GRADE_MAPPING.get(grade_code) - (current_star + 1)
                else:
                    range_empty_star = DAN_STAR_GRADE_MAPPING.get(grade_code) - current_star

                for _ in range(range_empty_star):
                    stars.append({'status': ''})

                for _ in range(current_star + 1 if win else current_star):
                    if win is not None:
                        if win:
                            stars.append({'status': 'through addStar'})
                        else:
                            # stars.append({'status': 'reduceStar'})
                            stars.append({'status': ''})

                        win = None
                    else:
                        stars.append({'status': 'through'})
            else:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        else:

            # 下一级锁定
            if grade_code == current_level + 1:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code < current_level:
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code == current_level:
                stars = [{'status': 'pass passStar'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            else:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]

        level_dict = {
            'id': grade_code,
            'name': name,
            'logo': logo,
            'if_lock': if_lock,
            'stars': stars,
            'cost': diamond_consume,
            'title': title
        }

        level_list.append(level_dict)

    return level_list


def get_dynamic_level_list2(current_level, current_star, win, unlock, diamond_consume_dict):
    """
    答题完成后的列表数据
    有相对应的css
    :param current_level:
    :param current_star:
    :param win:
    :param unlock:
    :param diamond_consume_dict:
    :return:
    """
    level_list = []

    # 默认显示下一级
    for grade_code in TYPE_DAN_GRADE_LIST:

        # name 地址
        name = '{protocol}://{host}{static_url}level{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)
        title = TYPE_DAN_GRADE_DICT.get(grade_code)
        # logo 地址
        logo = '{protocol}://{host}{static_url}sign{grade_code}.png'.format(
            protocol=SERVER_PROTOCOL, host=SERVER_HOST, static_url=MINI_APP_STATIC_URL_PREFIX, grade_code=grade_code)

        # 钻石消耗
        diamond_consume = diamond_consume_dict.get(grade_code, 0)

        # 是否锁
        if grade_code <= current_level:
            # 当前的答题段位大于该段位
            if_lock = 0
        else:
            # 没有解锁下一段位
            # 且该段位 等于 当前答题段位 + 1
            if_lock = 1

        # stars
        if not unlock:

            if grade_code == current_level + 1:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code < current_level:
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code == current_level:

                stars = []
                if win:
                    range_empty_star = DAN_STAR_GRADE_MAPPING.get(grade_code) - (current_star + 1)
                else:
                    range_empty_star = DAN_STAR_GRADE_MAPPING.get(grade_code) - current_star

                for _ in range(range_empty_star):
                    stars.append({'status': ''})

                for _ in range(current_star + 1 if win else current_star):
                    if win is not None:
                        if win:
                            stars.append({'status': 'through addStar'})
                        else:
                            # stars.append({'status': 'reduceStar'})
                            stars.append({'status': 'through'})

                        win = None
                    else:
                        stars.append({'status': 'through'})
            else:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
        else:

            # 下一级锁定
            if grade_code == current_level + 1:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code < current_level:
                stars = [{'status': 'pass'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            elif grade_code == current_level:
                stars = [{'status': 'pass passStar'} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]
            else:
                stars = [{'status': ''} for _ in range(DAN_STAR_GRADE_MAPPING.get(grade_code))]

        level_dict = {
            'id': grade_code,
            'name': name,
            'logo': logo,
            'if_lock': if_lock,
            'stars': stars,
            'cost': diamond_consume,
            'title': title
        }

        level_list.append(level_dict)

    return level_list


async def deal_with_own_answers(member, own_answers):
    """
    处理小程序提交答案
    :param member:
    :param own_answers:
    :return:
    """

    unlock = False

    answers = own_answers.get('answers', [])  # 答题数据
    pk_status = own_answers.get('pk_status')  # pk结果
    runaway_index = own_answers.get('runaway_index', '')  # 逃跑题目
    score = own_answers.get('score', 0)
    dan_grade = own_answers.get('grade')

    answer_list = []
    correct_list = []
    for answer in answers:
        temp_answer = {}
        temp_question = {}
        if answer:
            question_id = answer.get('questionid')
            temp_answer = {
                'subject_cid': answer.get('questionid'),
                'selected_option_cid': answer.get('optionid'),
                'consume_time': 20 - int(answer.get('remaintime', 0)),
                'score': int(answer.get('score', 0)),
                'true_answer': answer.get('true_answer')
            }
            if dan_grade:
                set_cached_subject_accuracy(question_id, answer.get('true_answer'))
            correct, error = get_cached_subject_accuracy(question_id)
            all_amount = correct + error
            percent = format(float(correct) / float(all_amount), '.2%') if all_amount else '0%'
            temp_question = {
                'question_id': question_id,
                'correct_percent': percent
            }
        answer_list.append(temp_answer)
        correct_list.append(temp_question)
        await subject_wrong_statistics(answer, member.cid)
    # 保存答题历史
    continuous_win_times = 0
    if dan_grade:
        member_game_history = MemberGameHistory()
        member_game_history.member_cid = member.cid
        member_game_history.result = answer_list
        member_game_history.status = int(pk_status)
        member_game_history.score = int(score)
        member_game_history.dan_grade = dan_grade
        member_game_history.fight_datetime = datetime.datetime.now()
        member_game_history.runaway_index = int(runaway_index) if runaway_index else None
        # 判断胜负以及解锁
        if member_game_history.status == STATUS_RESULT_GAME_PK_WIN:
            # 判断解锁
            current_dan_grade = member.dan_grade
            if current_dan_grade is None:
                current_dan_grade = TYPE_DAN_GRADE_ONE
            current_star_grade = member.star_grade
            if current_star_grade is None:
                current_star_grade = TYPE_STAR_GRADE_ONE
            else:
                current_star_grade += 1

            dan_grade_full_stars = DAN_STAR_GRADE_MAPPING.get(current_dan_grade)
            # 答题段位和当前段位一致，且满星了
            if dan_grade == current_dan_grade and current_star_grade >= dan_grade_full_stars:
                unlock = True
            # 判断连胜
            # 当前连胜次数
            last_pk_list = await MemberGameHistory.find({'member_cid': member.cid}).sort(
                [('fight_datetime', -1)]).limit(1).to_list(1)
            if last_pk_list and last_pk_list[0].continuous_win_times:
                member_game_history.continuous_win_times = last_pk_list[0].continuous_win_times + 1
            else:
                member_game_history.continuous_win_times = 1
        else:
            member_game_history.continuous_win_times = 0
        continuous_win_times = member_game_history.continuous_win_times  # 当前连胜

        await member_game_history.save()

        # 统计会员记录
        # await start_docking_statistics(member_game_history, member)
        start_accurate_statistics.delay(member_game_history, member)
        await start_dashboard_report_statistics(member_game_history, member)

    return int(pk_status), unlock, continuous_win_times, correct_list, member_game_history


async def subject_wrong_statistics(answer, member_cid):
    """
    记录错题信息
    :param answer:答案
    :param member_cid:用户cid
    :return:
    """
    true_answer = answer.get('true_answer')
    if true_answer is False:
        subject_cid = answer.get('questionid')
        selected_option_cid = answer.get('optionid')
        member_wrong_subject = await MemberWrongSubject.find(
            dict(member_cid=member_cid, subject_cid=subject_cid, option_cid=selected_option_cid)).to_list(None)
        if member_wrong_subject:
            await MemberWrongSubject.delete_many({
                'member_cid': member_cid,
                'subject_cid': subject_cid,
                'option_cid': selected_option_cid
            })
        member_wrong_subject = MemberWrongSubject(member_cid=member_cid, subject_cid=subject_cid,
                                                  option_cid=selected_option_cid)
        member_wrong_subject.wrong_dt = datetime.datetime.now()
        await member_wrong_subject.save()
    elif true_answer is True:
        selected_option_cid = answer.get('optionid')
        subject_cid = answer.get('questionid')
        member_wrong_subject_list = await MemberWrongSubject.find(
            dict(member_cid=member_cid, subject_cid=subject_cid)).to_list(None)
        if member_wrong_subject_list:
            for member_wrong_subject in member_wrong_subject_list:
                member_wrong_subject.option_cid = selected_option_cid
                member_wrong_subject.status = STATUS_WRONG_SUBJECT_INACTIVE
                await member_wrong_subject.save()


async def pk_award(member, pk_status, continuous_win_times):
    """
    处理pk钻石奖励
    首次PK，首次获胜，连胜奖励

    处理pk积分奖励
    首次pk 每日首次
    :param member:
    :param pk_status:
    :param continuous_win_times:
    :return:
    """
    total_diamond_reward = 0
    total_integral_reward = None
    diamond_reward_info = []
    # 判断是否首次pk
    fight_times = await MemberGameHistory.count(filtered={'member_cid': member.cid})
    if fight_times == 1:
        # 钻石
        _, first_pk_diamond = await do_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_FIRST_PK)
        total_diamond_reward += (first_pk_diamond if first_pk_diamond else 0)
        # 积分
        await do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_FIRST_KNOWLEDGE_PK)
        diamond_reward_info.append({'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_FIRST_PK),
                                    'diamond_num': first_pk_diamond if first_pk_diamond else 0
                                    })
    # 是否每日首次
    current_time = datetime.datetime.now()
    filter_dict = {
        'member.cid': member.cid,
        'fight_datetime': {
            '$gt': datetime.datetime(current_time.year, current_time.month, current_time.day, 0, 0, 0),
            '$lt': current_time,
        }
    }
    daily_times = await MemberGameHistory.count(filtered=filter_dict)
    if daily_times == 1:
        # 每日首次积分
        await do_integral_reward(member.cid, SOURCE_MEMBER_INTEGRAL_KNOWLEDGE_PK_EVERYDAY)

    # 判断是否首次获胜
    if fight_times == 1 and pk_status == STATUS_RESULT_GAME_PK_WIN:
        # 首次获胜钻石奖励
        _, first_win_diamond = await do_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_FIRST_WIN)
        total_diamond_reward += (first_win_diamond if first_win_diamond else 0)
        diamond_reward_info.append({'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_FIRST_WIN),
                                    'diamond_num': first_win_diamond if first_win_diamond else 0
                                    })

    # 判断连胜
    # 起始次数
    game_diamond_reward = await GameDiamondReward.find_one(filtered={'source': SOURCE_MEMBER_DIAMOND_WIN_STREAK_TIMES})
    if not game_diamond_reward or not game_diamond_reward.quantity:
        start_times = 0
    else:
        start_times = game_diamond_reward.quantity
    if start_times is not None and continuous_win_times >= start_times:
        # 起始奖励钻石
        start_award_obj = await GameDiamondReward.find_one({'source': SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_START})
        if not start_award_obj or not start_award_obj.quantity:
            start_award = 0
        else:
            start_award = start_award_obj.quantity
        # 每次连胜增加钻石
        every_award_obj = await GameDiamondReward.find_one({'source': SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND})
        if not every_award_obj:
            every_award = 0
        else:
            every_award = every_award_obj.quantity

        reward_diamond = start_award + (continuous_win_times - start_times) * every_award
        _, streak_diamond = await do_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_WIN_STREAK_AWARD_APPEND,
                                                    reward_diamond)
        total_diamond_reward += (streak_diamond if streak_diamond else 0)
        diamond_reward_info.append({'title': u'%s连胜' % continuous_win_times,
                                    'diamond_num': streak_diamond if streak_diamond else 0
                                    })
    return total_integral_reward, total_diamond_reward, diamond_reward_info


async def generate_image_answers(member, grade_id, question_cid_list):
    """
    根据用户，段位和问题编号生成镜像答题
    并返回小程序格式的数据
    :param member:
    :param grade_id:
    :param question_cid_list:
    :return:
    """

    opponent = {}
    opponent_answer_list = []

    game_history = MemberGameHistory()
    game_history.member_cid = member.cid
    game_history.status = STATUS_RESULT_GAME_PK_WIN
    game_history.pk_datetime = datetime.datetime.now()
    game_history.dan_grade = int(grade_id)
    game_history.status = random.choice([STATUS_RESULT_GAME_PK_WIN, STATUS_RESULT_GAME_PK_FAILED])

    score = 0

    result_list = []

    # 正确题目code list
    _, correct_question_cid_list = get_random_question_data(int(grade_id), question_cid_list)

    for question_cid in question_cid_list:
        option_query_dict = {'subject_cid': question_cid}
        if question_cid in correct_question_cid_list:
            # 正确
            option_query_dict['correct'] = True
        else:
            # 错误
            option_query_dict['correct'] = False

        option_list = await SubjectOption.find(option_query_dict).to_list(None)
        if option_list:
            option = random.choice(option_list)
        else:
            option = {}

        remain_time, _ = get_random_question_data(int(grade_id), None)
        if option.correct:
            question_score = remain_time * 20
        else:
            question_score = 0

        consume_time = 20 - remain_time

        result = {
            'subject_cid': question_cid,
            'selected_option_cid': option.cid,
            'consume_time': consume_time,
            'score': question_score,
            'true_answer': option.correct
        }

        score += question_score
        result_list.append(result)

        # 返回的格式数据
        opponent_answer = {
            'remaintime': remain_time,
            'questionid': question_cid,
            'optionid': result.get('selected_option_cid'),
            'true_answer': result.get('true_answer'),
            'score': question_score,
        }
        opponent_answer_list.append(opponent_answer)

    game_history.score = score
    game_history.runaway_index = ''
    game_history.result = result_list

    opponent['score'] = 0  # 默认是0
    opponent['runaway_index'] = ''
    opponent['answers'] = opponent_answer_list

    return opponent


async def update_member_pk_info(member, pk_status, unlock, grade_id):
    """
    根据pk结果来更新用户的pk信息
    :param member:
    :param pk_status:
    :param unlock:
    :param grade_id:
    :return:
    """
    fight_times = int(member.fight_times) + 1 if member.fight_times else 1
    win_times = int(member.win_times) + 1 if member.win_times else 1
    win_percent = float(win_times / fight_times)

    member.fight_times = fight_times
    member.win_times = win_times
    member.win_percent = win_percent
    member.updated_dt = datetime.datetime.now()

    diamond_changes = 0  # 钻石相关
    current_star_diamond = member.diamond
    diamond_consume_obj = await GameDiamondConsume.find_one(filtered={'source': grade_id})
    diamond_consume = diamond_consume_obj.quantity

    current_star_grade = member.star_grade if member.star_grade else 0  # 当前星级
    current_dan_grade = member.dan_grade
    if pk_status == STATUS_RESULT_GAME_PK_WIN:
        if unlock:  # 段位 + 1
            if current_dan_grade:
                if current_dan_grade < TYPE_DAN_GRADE_ELEVEN:
                    member.dan_grade = current_dan_grade + 1
                    member.star_grade = 0
                else:
                    # if current_star_grade < DAN_STAR_GRADE_MAPPING.get(current_dan_grade):
                    #     member.star_grade = current_star_grade + 1
                    member.star_grade = current_star_grade + 1
            else:
                member.dan_grade = TYPE_DAN_GRADE_ONE
        else:
            # 答题段位是当前段位时，星级 + 1，否则不加
            if current_dan_grade == grade_id:
                member.star_grade = current_star_grade + 1  # 星级 + 1
        # 增加钻石
        diamond_changes = diamond_consume  # 返回钻石为入场费
        member.diamond = current_star_diamond + (diamond_consume * 2)  # 实际钻石更新为两倍
        # 更新钻石奖励历史
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, diamond_consume)
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_VICTORY, diamond_consume)
    elif pk_status in [STATUS_RESULT_GAME_PK_FAILED, STATUS_RESULT_GAME_PK_GIVE_UP]:
        # 星星数扣减
        # if current_dan_grade == grade_id:
        #     member.star_grade = current_star_grade - 1 if current_star_grade else 0  # 星级-1
        # 扣除钻石，实际已经处理
        diamond_changes = diamond_consume
    elif pk_status == STATUS_RESULT_GAME_PK_TIE_BREAK:
        # 返还入场费
        member.diamond = current_star_diamond + diamond_consume
        # 更新钻石奖励历史
        await update_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_PK_ENTRANCE_FEE_RETURN, diamond_consume)

    pk_history_list = await MemberGameHistory.find({
        'member_cid': member.cid,
        'continuous_win_times': {'$ne': None}
    }).sort([('continuous_win_times', DESC)]).limit(1).to_list(1)

    if pk_history_list:
        pk_history = pk_history_list[0]
    else:
        pk_history = {}

    continuous_win_times = pk_history.continuous_win_times  # 最大连胜
    current_highest_win_times = member.highest_win_times
    if not current_highest_win_times or (
            current_highest_win_times and current_highest_win_times < continuous_win_times):
        member.highest_win_times = continuous_win_times
    await member.save()
    return diamond_changes


def get_random_question_data(grade, question_cid_list):
    """
    根据段位获取剩余时间, 答对的题目code
    :param grade:
    :param question_cid_list:
    :return:
    """
    if grade == TYPE_DAN_GRADE_ONE:
        rate_consume_time_list = [(0.3, (2, 3)), (0.6, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_TWO:
        rate_consume_time_list = [(0.3, (2, 3)), (0.6, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_THIRD:
        rate_consume_time_list = [(0.3, (2, 3)), (0.6, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_FOUR:
        rate_consume_time_list = [(0.3, (2, 3)), (0.6, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_FIVE:
        rate_consume_time_list = [(0.5, (2, 3)), (0.4, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_SIX:
        rate_consume_time_list = [(0.5, (2, 3)), (0.4, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0, 1), (0, 2), (0.4, 3), (0.4, 4), (0.2, 5)]

    elif grade == TYPE_DAN_GRADE_SEVEN:
        rate_consume_time_list = [(0.5, (2, 3)), (0.4, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0.05, 1), (0.1, 2), (0.15, 3), (0.35, 4), (0.35, 5)]

    elif grade == TYPE_DAN_GRADE_EIGHT:
        rate_consume_time_list = [(0.5, (2, 3)), (0.4, (3, 6)), (0.1, (6, 9))]
        rate_amount_list = [(0.05, 1), (0.1, 2), (0.15, 3), (0.25, 4), (0.45, 5)]

    elif grade == TYPE_DAN_GRADE_NINE:
        rate_consume_time_list = [(0.7, (2, 3)), (0.3, (3, 6))]
        rate_amount_list = [(0, 1), (0, 2), (0.05, 3), (0.1, 4), (0.85, 5)]

    elif grade == TYPE_DAN_GRADE_TEN:
        rate_consume_time_list = [(0.8, (2, 3)), (0.2, (3, 6))]
        rate_amount_list = [(0, 1), (0, 2), (0, 3), (0.1, 4), (0.9, 5)]

    elif grade == TYPE_DAN_GRADE_ELEVEN:
        rate_consume_time_list = [(0.9, (2, 3)), (0.1, (3, 6))]
        rate_amount_list = [(0, 1), (0, 2), (0, 3), (0.05, 4), (0.95, 5)]

    else:
        rate_consume_time_list = [(0.3, (1, 3)), (0.4, (3, 6)), (0.3, (6, 10))]
        rate_amount_list = [(0.2, 5), (0.2, 4), (0.2, 3), (0.2, 2), (0.2, 1)]
    correct_question_cid_list = []  # 答对题目数量
    remain_time = 20 - random.randint(1, 9)  # 剩余时间
    if question_cid_list is not None:
        correct_amount = pick_rate_element(rate_amount_list)  # 答对题目数量
        if correct_amount:
            try:
                correct_question_cid_list = random.sample(question_cid_list, correct_amount)
            except ValueError:
                correct_question_cid_list = []
    else:
        consume_time_t = pick_rate_element(rate_consume_time_list)
        if consume_time_t:
            remain_time = 20 - random.randint(*consume_time_t)
    return remain_time, correct_question_cid_list


def pick_rate_element(rate_element_list):
    """
    根据有序概率列表返回元素
    :param rate_element_list: [(0, 4), (0, 5), (0.1, 3), (0.2, 2), (0.7, 1)]
    :return:
    """

    correct_amount = None

    x = random.random()
    current = 0.0

    for rate, amount in rate_element_list:
        current += rate
        correct_amount = amount
        if x < current:
            break

    return correct_amount


async def do_integral_reward(member_cid, source_integral, integral=None):
    if not isinstance(member_cid, (str, bytes)):
        raise ValueError('Parameter member_cid must be a type of str or bytes.')
    if source_integral not in SOURCE_MEMBER_INTEGRAL_LIST:
        raise ValueError('Parameter source_integral must in %s.' % str(SOURCE_MEMBER_INTEGRAL_LIST))
    if integral and not isinstance(integral, (int, float)):
        raise TypeError('Parameter integral must be type of int or float.')
    m_integral = integral
    if integral is None:
        integral_reward_obj = await MemberIntegralSource.find_one(filtered={'source': source_integral})
        if integral_reward_obj:
            m_integral = integral_reward_obj.integral
    if not m_integral:
        m_integral = 0

    member = await Member.get_by_cid(member_cid)
    if member:
        member.integral = member.integral + m_integral
        member.updated_dt = datetime.datetime.now()

        integral_detail = MemberIntegralDetail()
        integral_detail.member_cid = member.cid
        integral_detail.integral = m_integral
        integral_detail.source = source_integral
        integral_detail.reward_datetime = datetime.datetime.now()
        integral_detail.content = SOURCE_MEMBER_INTEGRAL_DICT.get(source_integral)

        await integral_detail.save()
        await member.save()

        return True, m_integral
    return False, None


async def do_diamond_reward(member_cid, source_diamond, diamond=None):
    if not isinstance(member_cid, (str, bytes)):
        raise ValueError('Parameter member_cid must be a type of str or bytes.')
    if source_diamond not in SOURCE_MEMBER_DIAMOND_LIST:
        raise ValueError('Parameter source_diamond must in %s.' % str(SOURCE_MEMBER_DIAMOND_LIST))
    if diamond and not isinstance(diamond, (int, float)):
        raise TypeError('Parameter diamond must be type of int or float.')
    m_diamond = diamond
    if diamond is None:
        diamond_reward_obj = await GameDiamondReward.find_one(filtered={'source': source_diamond})
        if diamond_reward_obj:
            m_diamond = diamond_reward_obj.quantity
    if not m_diamond:
        m_diamond = 0

    member = await Member.get_by_cid(member_cid)
    if member:
        member.diamond = member.diamond + m_diamond
        member.updated_dt = datetime.datetime.now()

        diamond_detail = MemberDiamondDetail()
        diamond_detail.member_cid = member.cid
        diamond_detail.diamond = m_diamond
        diamond_detail.source = source_diamond
        diamond_detail.reward_datetime = datetime.datetime.now()
        diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)

        await diamond_detail.save()
        await member.save()

        return True, m_diamond
    return False, None


async def update_diamond_reward(member_cid, source_diamond, diamond=0):
    diamond_detail = MemberDiamondDetail()
    diamond_detail.member_cid = member_cid
    diamond_detail.diamond = diamond
    diamond_detail.source = source_diamond
    diamond_detail.reward_datetime = datetime.datetime.now()
    diamond_detail.content = SOURCE_MEMBER_DIAMOND_DICT.get(source_diamond)

    await diamond_detail.save()


async def generate_opponent_answers(opponent):
    """
    根据用户，段位和问题编号生成镜像答题
    并返回小程序格式的数据
    :param opponent:
    :return:
    """
    opponent_result = {}
    question_list = []
    opponent_answer_list = []
    fight_result_dict = {}
    init_own_answer_list = []
    fight_subject_cid_list = []
    game_history_list = await MemberGameHistory.aggregate([
        MatchStage({'member_cid': opponent.cid, 'runaway_index': None}),
        SortStage([('dan_grade', DESC), ('created_dt', DESC)]),
        LimitStage(1)
    ]).to_list(1)

    if game_history_list:
        game_history = game_history_list[0]
        if game_history:
            fight_result_list = game_history.result
            if fight_result_list:
                for fight_result in fight_result_list:
                    fight_result_dict[fight_result.get('subject_cid')] = fight_result
                    fight_subject_cid_list.append(fight_result.get('subject_cid'))
    if fight_result_dict:
        subject_dict = {}
        subject_list = await Subject.aggregate([
            MatchStage({'cid': {'$in': fight_subject_cid_list}}),
            LookupStage(SubjectOption, let={'cid': '$cid'},
                        pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                  {'$sort': {'code': ASC}}], as_list_name='option_list'),
            LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')
        ]).to_list(None)
        for temp in subject_list:
            subject_dict[temp.cid] = temp
        if fight_subject_cid_list:
            for index, subject_cid in enumerate(fight_subject_cid_list):
                subject = subject_dict.get(subject_cid)
                if subject:
                    init_own_answer_list.append({'questionid': subject.cid})
                    question = deal_subject(subject, index == 0)
                    if question:
                        result = fight_result_dict.get(subject.cid)
                        if result:
                            o_answer = {
                                'remain_time': 20 - result.get('consume_time', 0),
                                'question_id': subject.cid,
                                'option_id': result.get('selected_option_cid'),
                                'true_answer': result.get('true_answer'),
                                'score': result.get('score', 0)
                            }
                            opponent_answer_list.append(o_answer)
                            question_list.append(question)

    opponent_result['score'] = 0  # 默认是0
    opponent_result['runaway_index'] = ''
    opponent_result['answers'] = opponent_answer_list

    return opponent_result, question_list, init_own_answer_list


def deal_subject(subject, is_current=False):
    if subject:
        title_picture = subject.file_list[0].title if subject.file_list else ''
        if title_picture:
            title_picture_url = '%s://%s%s%s%s' % (
                SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/', title_picture)
        else:
            title_picture_url = ''
        difficulty = subject.difficulty
        difficulty_list = []
        for i in range(1, 6):
            if difficulty >= i:
                temp_difficulty = {
                    'show': 'star_degree'
                }
            else:
                temp_difficulty = {
                    'show': ''
                }
            difficulty_list.append(temp_difficulty)

        question = {
            'id': subject.cid,
            'title': subject.title,
            'picture_url': title_picture_url,
            'category_name': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category),
            'is_current': is_current,
            'timeout': 20,
            'difficulty_list': difficulty_list,
            'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
            'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
            'resolving': subject.resolving
        }
        option_doc_list = subject.option_list
        option_list = []
        for option_doc in option_doc_list:
            option = {
                'title': option_doc.title,
                'id': option_doc.cid,
                'true_answer': option_doc.correct if option_doc.correct else False,
                'option_show': ''
            }
            option_list.append(option)
        question['option_list'] = option_list

        return question
    return {}


def set_cached_subject_accuracy(subject_code, correct=False):
    """
     # 缓存题目结果便于统计
    :param subject_code: 题目编号
    :param correct: 是否回答正确
    :return:
    """

    if subject_code:
        cache_key = '%s-E' % subject_code
        if correct:
            cache_key = '%s-C' % subject_code
        value = RedisCache.hget(KEY_CACHE_SUBJECT_RESULT, cache_key)
        if not value:
            value = 0
        value = int(value) + 1
        RedisCache.hset(KEY_CACHE_SUBJECT_RESULT, cache_key, value)


def get_cached_subject_accuracy(subject_code):
    """
    获取题目缓存结果
    :param subject_code: 题目编号
    :return: (正确数量， 错误数量)
    """
    if subject_code:
        correct, error = RedisCache.hmget(KEY_CACHE_SUBJECT_RESULT, ('%s-C' % subject_code, '%s-E' % subject_code))
        if not correct:
            correct = 0
        if not error:
            error = 0
        return int(correct), int(error)
    return 0, 0


def get_member_all_star(member):
    """
    :param member: 会员
    :return: 用户会员已获得的星星
    """
    star_grade = member.star_grade  # 当前星数
    dan_grade = member.dan_grade
    if dan_grade in TYPE_DAN_GRADE_LIST:
        dan_grade_index = TYPE_DAN_GRADE_LIST.index(dan_grade)
        all_star = star_grade
        for i in range(dan_grade_index):
            temp_dan = TYPE_DAN_GRADE_LIST[i]
            temp_star = DAN_STAR_GRADE_MAPPING.get(temp_dan, 0)
            all_star += temp_star
        return all_star
    return 0


async def deal_wrong_questions(question_cid_list):
    """
    根据题目code处理错题信息
    :param question_cid_list:
    :return:
    """
    question_list = []
    is_current = True
    for question_cid, option_cid in question_cid_list:
        subject_list = await Subject.aggregate(
            [
                MatchStage(dict(cid=question_cid)),
                LookupStage(SubjectOption, 'cid', 'subject_cid', 'option_list'),
                LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')
            ]
        ).to_list(1)

        if subject_list:
            subject = subject_list[0]
            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''
            difficulty = subject.difficulty
            difficulty_list = []
            for i in range(1, 6):
                if difficulty >= i:
                    temp_difficulty = {
                        'show': 'star_degree'
                    }
                else:
                    temp_difficulty = {
                        'show': ''
                    }
                difficulty_list.append(temp_difficulty)

            correct, error = get_cached_subject_accuracy(question_cid)
            all_amount = correct + error
            percent = format(float(correct) / float(all_amount), '.2%') if all_amount else '0%'
            question = {
                'id': subject.cid,
                'title': subject.title,
                'title_picture_url': title_picture_url,
                'subject_type': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category),
                'is_current': is_current,
                'total_time': 20,
                'difficulty_list': difficulty_list,
                'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
                'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
                'resolving': subject.resolving,
                'correct_percent': percent,
                'analysis_box_show': False,
                'analysis_btn': True,
                'option_cid': option_cid
            }

            is_current = False

            option_doc_list = subject.option_list if subject.option_list else []
            option_list = []
            for option_doc in option_doc_list:
                option = {
                    'title': option_doc.title,
                    'id': option_doc.cid,
                    'true_answer': option_doc.correct,
                    'option_show': ''
                }
                option_list.append(option)

            question['options'] = option_list
            question_list.append(question)

    return question_list


async def do_daily_ranking_award(member):
    """
    每日排行榜奖励
    :param member:
    :return:奖励信息
    """
    reward_dict = {}
    start_datetime = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = datetime.datetime.now().replace(hour=23, minute=59, second=59, microsecond=99999)
    count = await MemberDiamondDetail.count({
        "member_cid": member.cid,
        "source": SOURCE_MEMBER_DIAMOND_DAILY_RANKING,
        "reward_datetime": {'$gte': start_datetime, '$lte': end_datetime},
    })
    if count == 0:
        ranking_limit = 0
        ranking_obj = await GameDiamondReward.find_one(
            filtered={'source': SOURCE_MEMBER_DIAMOND_DAILY_RANKING_VALUE_LIMIT})
        if ranking_obj:
            ranking_limit = ranking_obj.quantity

        members = await Member.find({'status': STATUS_USER_ACTIVE}).sort(
            [('dan_grade', -1), ('star_grade', -1)]).limit(ranking_limit).to_list(ranking_limit)
        for temp_member in members:
            if member.cid == temp_member.cid:
                _, m_diamond = await do_diamond_reward(member.cid, SOURCE_MEMBER_DIAMOND_DAILY_RANKING)
                member.updated_dt = datetime.datetime.now()

                member.diamond = member.diamond + m_diamond
                await member.save()

                reward_dict = {
                    'title': SOURCE_MEMBER_DIAMOND_DICT.get(SOURCE_MEMBER_DIAMOND_DAILY_RANKING),
                    'diamond_num': m_diamond
                }
    return reward_dict


async def deal_game_checkpoint_subjects(subject_cid_list):
    """
    处理关卡的题目信息
    :param subject_cid_list:
    :return: 题目列表
    """
    match = MatchStage({'status': STATUS_SUBJECT_ACTIVE, 'cid': {'$in': subject_cid_list},
                        'category_use': {'$ne': {'$in': [CATEGORY_SUBJECT_BENCHMARK, CATEGORY_SUBJECT_GRADUATION]}}})
    option_lookup = LookupStage(SubjectOption, let={'cid': '$cid'},
                                pipeline=[{'$match': {'$expr': {'$and': [{'$eq': ['$subject_cid', '$$cid']}]}}},
                                          SortStage([('code', ASC)])], as_list_name='option_list')
    image_lookup = LookupStage(UploadFiles, 'image_cid', 'cid', 'file_list')
    sample = SampleStage(len(subject_cid_list))
    subject_list = await Subject.aggregate([match, option_lookup, image_lookup, sample]).to_list(None)
    question_list = []
    for subject in subject_list:
        if subject:
            title_picture = subject.file_list[0].title if subject.file_list else ''
            if title_picture:
                title_picture_url = '%s://%s%s%s%s' % (SERVER_PROTOCOL, SERVER_HOST, STATIC_URL_PREFIX, 'files/',
                                                       title_picture)
            else:
                title_picture_url = ''
            difficulty = subject.difficulty
            difficulty_list = []
            for subject_difficulty in CODE_SUBJECT_DIFFICULTY_LIST:
                if difficulty >= subject_difficulty:
                    temp_difficulty = {
                        'show': 'star_degree'
                    }
                else:
                    temp_difficulty = {
                        'show': ''
                    }
                difficulty_list.append(temp_difficulty)

            question = {
                'id': subject.cid,
                'title': subject.title,
                'picture_url': title_picture_url,
                'category_name': CATEGORY_SUBJECT_KNOWLEDGE_DICT.get(subject.category),
                'timeout': 20,
                'difficulty_list': difficulty_list,
                'knowledge_first': KNOWLEDGE_FIRST_LEVEL_DICT.get(subject.knowledge_first),
                'knowledge_second': KNOWLEDGE_SECOND_LEVEL_DICT.get(subject.knowledge_second),
                'resolving': subject.resolving
            }
            option_doc_list = subject.option_list if subject.option_list else []
            option_list = []
            for option_doc in option_doc_list:
                option = {
                    'id': option_doc.cid,
                    'title': option_doc.title,
                    'true_answer': option_doc.correct,
                    'option_show': ''
                }
                option_list.append(option)

            question['option_list'] = option_list
            question_list.append(question)

    return question_list


def get_next_game_checkpoint_cid(game_checkpoints, member_checkpoint_cid):
    """
    下一关
    :param game_checkpoints:
    :param member_checkpoint_cid:用户当前已通过的关卡
    :return:
    """
    game_checkpoint_cid_list = [game_checkpoint.cid for game_checkpoint in game_checkpoints]
    next_game_checkpoint_cid = None
    if member_checkpoint_cid in game_checkpoint_cid_list:
        member_index = game_checkpoint_cid_list.index(member_checkpoint_cid)
        next_index = member_index - 1
        if next_index >= 0:
            next_game_checkpoint_cid = game_checkpoint_cid_list[next_index]
        else:
            next_game_checkpoint_cid = game_checkpoint_cid_list[0]
    return next_game_checkpoint_cid


async def deal_checkpoint_own_answer(race_cid, member, own_answers, checkpoint_cid):
    """
    处理竞赛答案数据
    :param race_cid:
    :param member:
    :param own_answers:
    :param checkpoint_cid:
    :return: 是否解锁下一关
    """
    is_challenge_success = False
    unlock = False
    is_end = False
    answers = own_answers.get('answers', [])  # 答题数据
    pk_status = own_answers.get('pk_status')  # pk结果
    score = own_answers.get('score', 0)
    answer_list = []
    game_checkpoint = await RaceGameCheckPoint.find_one(dict(cid=checkpoint_cid))
    unlock_quantity = game_checkpoint.unlock_quantity

    mapping = await RaceMapping.find_one(
        {'race_cid': game_checkpoint.race_cid, 'member_cid': member.cid, 'record_flag': 1})
    answer_correct_num = 0
    question_accuracy = {}
    for answer in answers:
        temp_answer = {}
        if answer:
            question_id = answer.get('question_id')
            temp_answer = {
                'subject_cid': question_id,
                'selected_option_cid': answer.get('option_id'),
                'consume_time': 20 - int(answer.get('remain_time', 0)),
                'score': int(answer.get('score', 0)),
                'true_answer': answer.get('true_answer')
            }

            if answer.get('true_answer'):
                answer_correct_num += 1
                mapping.total_correct += 1
            if answer.get('true_answer') != None:
                mapping.total_count += 1
            await mapping.save()
            set_cached_subject_accuracy(question_id, answer.get('true_answer'))
            correct, error = get_cached_subject_accuracy(question_id)
            all_amount = correct + error
            percent = format(float(correct) / float(all_amount), '.2%') if all_amount else '0%'
            question_accuracy[question_id] = percent

        answer_list.append(temp_answer)
    # 判断当前答题关卡与用户目前关卡
    if checkpoint_cid or mapping.race_check_point_cid is None:
        if int(pk_status) != STATUS_RESULT_GAME_PK_GIVE_UP:
            if answer_correct_num >= unlock_quantity:
                is_challenge_success = True

                checkpoint_list = await RaceGameCheckPoint.find(
                    dict(race_cid=game_checkpoint.race_cid, status=STATUS_GAME_CHECK_POINT_ACTIVE)).sort(
                    [('index', ASC)]).to_list(None)
                checkpoint_cid_list = [checkpoint.cid for checkpoint in checkpoint_list]
                # 当前答题的关卡
                index = 0
                if checkpoint_cid in checkpoint_cid_list:
                    index = checkpoint_cid_list.index(checkpoint_cid)
                # 用户所在的关卡
                cur_checkpoint_index = 0
                if mapping.race_check_point_cid in checkpoint_cid_list:
                    cur_checkpoint_index = checkpoint_cid_list.index(mapping.race_check_point_cid)
                # 解锁下一关卡
                if index >= cur_checkpoint_index:
                    # 没闯过的关
                    next_checkpoint_index = cur_checkpoint_index + 1
                    if next_checkpoint_index <= (len(checkpoint_cid_list) - 1):
                        # 至少还有一关可以闯时, 解锁
                        next_checkpoint_cid = checkpoint_cid_list[next_checkpoint_index]
                        mapping.race_check_point_cid = next_checkpoint_cid
                        await mapping.save()
                        unlock = True
                    else:
                        # 是否第一次通关
                        win_count = await MemberCheckPointHistory.count(
                            {'member_cid': member.cid, 'check_point_cid': checkpoint_cid,
                             'status': STATUS_RESULT_CHECK_POINT_WIN})
                        if win_count == 0:
                            unlock = True

                        if win_count == 1:
                            last_history = await MemberCheckPointHistory.find(
                                {'member_cid': member.cid, 'check_point_cid': checkpoint_cid}).to_list(1)
                            if last_history[0].status == STATUS_RESULT_CHECK_POINT_WIN:
                                unlock = True

                        is_end = True
                else:
                    # 在闯已经闯过的关
                    unlock = False
                    is_end = False

    # 保存关卡答题记录
    member_checkpoint_history = MemberCheckPointHistory()
    member_checkpoint_history.member_cid = member.cid
    member_checkpoint_history.result = answer_list
    member_checkpoint_history.status = int(pk_status)
    member_checkpoint_history.score = int(score)
    member_checkpoint_history.check_point_cid = checkpoint_cid
    member_checkpoint_history.fight_datetime = datetime.datetime.now()
    await member_checkpoint_history.save()
    # 统计会员记录
    start_accurate_statistics.delay(member_checkpoint_history, member)
    # 小程序数据不计入报表数据
    # await start_dashboard_report_statistics(member_checkpoint_history, member)
    await do_race_report(mapping, member, member_checkpoint_history, is_end)

    task_robot_analysis_reference_statistics(member_checkpoint_history, member)

    stat = await RaceCheckPointStatistics.find_one({'race_cid': mapping.race_cid, 'member_cid': member.cid})
    if not stat:
        stat = RaceCheckPointStatistics(race_cid=mapping.race_cid, member_cid=member.cid)

    if is_challenge_success:
        if stat.checkpoint_stat.get(checkpoint_cid) is None:
            stat.checkpoint_stat[checkpoint_cid] = answer_correct_num
            stat.correct_num = sum(list(stat.checkpoint_stat.values()))
        stat.pass_checkpoint_num = len(stat.checkpoint_stat)

    await stat.save()
    return unlock, is_end, is_challenge_success, question_accuracy


async def do_race_report(mapping: RaceMapping, member: Member, his: MemberCheckPointHistory, is_end):
    """
    活动报表数据统计
    :param mapping:
    :param member:
    :param his:
    :param is_end:
    :return:
    """
    race_cid = mapping.race_cid
    daily_code = get_daily_code(datetime.datetime.now())

    auth_address = mapping.auth_address
    if not auth_address:
        return

    param = {'race_cid': race_cid, 'province': auth_address.get('province'),
             'city': auth_address.get('city'), 'district': auth_address.get('district'),
             'town': auth_address.get('town'), 'sex': mapping.sex, 'education': mapping.education,
             'category': mapping.category, 'daily_code': daily_code, 'company_cid': mapping.company_cid}
    stat = await ReportRacePeopleStatistics.find_one(param, read_preference=ReadPreference.PRIMARY)

    if not stat:
        stat = ReportRacePeopleStatistics(**param)

    stat.total_num += 1

    cache_key = md5('race_report_daily_people_count_' + mapping.member_cid)
    if RedisCache.get(cache_key) is None:
        # 有效时间为当天
        valid_time = datetime.datetime.now().replace(hour=23, minute=59, second=59,
                                                     microsecond=999) - datetime.datetime.now()
        RedisCache.set(cache_key, 1, valid_time)
        stat.people_num += 1

    # 初次通关
    if is_end and his.status == STATUS_RESULT_CHECK_POINT_WIN and await MemberCheckPointHistory.count(
            {'status': STATUS_RESULT_CHECK_POINT_WIN, 'member_cid': mapping.member_cid,
             'check_point_cid': his.check_point_cid},
            read_preference=ReadPreference.PRIMARY) == 1:
        stat.pass_num += 1

    await stat.save()


def get_daily_code(dt):
    """
    获取对接标识
    :return:
    """
    return datetime2str(dt, date_format='%Y%m%d')
