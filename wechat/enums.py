# !/usr/bin/python
# -*- coding:utf-8 -*-
from settings import APP_ID, APP_SECRET, MINI_APP_ID, MINI_APP_SECRET

KEY_WECHAT_ACCESS_TOKEN_CACHE = 'ACCESS_TOKEN'  # AccessToken的缓存key
KEY_MINIAPP_ACCESS_TOKEN_CACHE = 'MINIAPP_ACCESS_TOKEN'  # 小程序AccessToken的缓存key

API_ACCESS_TOKEN_URL = 'https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s' % (
    APP_ID, APP_SECRET)  # 获取Access Token， 有效期7200s
API_MENU_CREATE_URL = 'https://api.weixin.qq.com/cgi-bin/menu/create?access_token=%s'  # 菜单创建
API_OAUTH_CODE_GET_URL = 'https://open.weixin.qq.com/connect/oauth2/authorize?appid=%s&redirect_uri=%s&response_type=' \
                         'code&scope=snsapi_base&state=%s#wechat_redirect'  # 获取网页授权CODE
API_CODE_EXCHANGE_ACCESS_TOKEN_URL = 'https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s' \
                                     '&grant_type=authorization_code'  # code换取Access Token
API_CODE_EXCHANGE_SESSION_URL = 'https://api.weixin.qq.com/sns/jscode2session?appid={app_id}&secret={app_secret}' \
                                '&js_code={code}&grant_type=authorization_code'  # 小程序code换取Session ID
API_USER_INFO_GET_URL = 'https://api.weixin.qq.com/sns/userinfo?access_token={ACCESS_TOKEN}&openid={OPENID}' \
                        '&lang=zh_CN'  # 获取用户信息请求
API_MEDIA_UPLOAD_URL = 'http://file.api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}' \
                       '&type={media_type}'  # 上传媒体文件
API_PIC_TXT_MATERIAL_UPLOAD_URL = 'https://api.weixin.qq.com/cgi-bin/media/uploadnews?access_token=%s'  # 上传图文素材
API_PUSH_PIC_TXT_MESSAGE_URL = 'https://api.weixin.qq.com/cgi-bin/message/mass/send?access_token=%s'  # 推送图文消息
API_PUSH_TEMPLATE_MESSAGE_URL = 'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token=%s'  # 推送模板消息
# 请求code url
API_CODE_URL = 'https://open.weixin.qq.com/connect/oauth2/authorize?appid={APPID}&redirect_uri={REDIRECT_URI}&' \
               'response_type=code&scope={SCOPE}&state={STATE}#wechat_redirect'
# 用户access_token请求url
API_USER_ACCESS_TOKEN_URL = 'https://api.weixin.qq.com/sns/oauth2/access_token?appid={APPID}&secret={SECRET}&' \
                            'code={CODE}&grant_type=authorization_code'

QR_GET_ACCESS_TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid=%s&secret=%s" % (
                        MINI_APP_ID, MINI_APP_SECRET)

QR_POST_URL = "https://api.weixin.qq.com/wxa/getwxacodeunlimit?access_token={token}"

# 小程序静态图片URL prefix
MINI_APP_STATIC_URL_PREFIX = '/static/images/games/'

# 微信事件
EVENT_WECHAT_SUBSCRIBE = 1  # 关注服务号
EVENT_WECHAT_LOCATION = 2  # 获取定位信息
EVENT_WECHAT_LATEST_SURVEY = 3  # 获取最新的可参与调查（问卷）
EVENT_WECHAT_SIGN_IN = 4  # 签到

# 微信菜单KEY
KEY_WECHAT_MENU_SURVEY_LATEST = 'MID0101'
KEY_WECHAT_MENU_SURVEY_HISTORY = 'MID0102'
KEY_WECHAT_MENU_SIGN_IN = 'MID0103'
KEY_WECHAT_MENU_AUTO_OWNER_AUTH = 'MID0104'
KEY_WECHAT_MENU_AUTO_KNOWLEDGE_PK = 'MID0201'
KEY_WECHAT_MENU_INTEGRAL_CENTRE = 'MID0301'

# 微信操作类型
TYPE_WECHAT_OPERATE_SURVEY_HISTORY_GET = 1
TYPE_WECHAT_OPERATE_INTEGRAL_CENTRE = 2
TYPE_WECHAT_OPERATE_TO_SURVEY = 3
TYPE_WECHAT_OPERATE_LIST = [
    TYPE_WECHAT_OPERATE_SURVEY_HISTORY_GET,
    TYPE_WECHAT_OPERATE_INTEGRAL_CENTRE,
    TYPE_WECHAT_OPERATE_TO_SURVEY
]
TYPE_WECHAT_OPERATE_DICT = {
    TYPE_WECHAT_OPERATE_SURVEY_HISTORY_GET: u'获取问卷历史',
    TYPE_WECHAT_OPERATE_INTEGRAL_CENTRE: u'积分中心',
    TYPE_WECHAT_OPERATE_TO_SURVEY: u'参与调研'
}
