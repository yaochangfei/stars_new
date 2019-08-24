import re
import traceback

from tornado.web import url

from commons import msg_utils

from logger import log_utils
from web import decorators, WechatAppletHandler

logger = log_utils.get_logging()


class RaceMobileValidateViewHandler(WechatAppletHandler):
    """
    发送验证码
    """

    @decorators.render_json
    @decorators.wechat_applet_authenticated
    async def post(self):
        r_dict = {'code': 0}
        try:
            mobile = self.get_i_argument('mobile', '')
            ret = re.match(r"^1[35678]\d{9}$", mobile)
            if mobile:
                _, verify_code = msg_utils.send_digit_verify_code(mobile, valid_sec=60)
                if verify_code:
                    r_dict['code'] = 1000
                    logger.info('mobile:%s,verify_code:%s' % (mobile, verify_code))
                else:
                    r_dict['code'] = 1003  # 验证码发送失败
                if not ret:
                    r_dict['code'] = 1002  # 手机号码格式不对
            else:
                r_dict['code'] = 1001  # 手机号为空
        except Exception:
            logger.error(traceback.format_exc())
        return r_dict


URL_MAPPING_LIST = [
    url(r'/race/send/msg/mobile/validate/', RaceMobileValidateViewHandler, name='race_send_msg_mobile_validate'),
]