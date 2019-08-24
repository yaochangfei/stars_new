#!/usr/bin/python
# -*- coding:utf-8 -*-
import smtplib
import traceback
from email import encoders
from email.header import Header
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from smtpd import COMMASPACE

import os

import settings
from db.models import InstantMail

STATUS_MAIL_SEND_FAILED = -1  # 失败的
STATUS_MAIL_SEND_SUCCEED = 1  # 成功的
STATUS_MAIL_SERVER_ERROR = 2  # 邮件服务器配置错误
STATUS_MAIL_SERVER_HOST_ERROR = 3  # 邮件服务器host为空
STATUS_MAIL_SERVER_USERNAME_ERROR = 4  # 邮件服务器用户名为空
STATUS_MAIL_SERVER_PASSWORD_ERROR = 5  # 邮件服务器密码为空
STATUS_MAIL_SUBJECT_NONE_ERROR = 6  # 邮件主题为空
STATUS_MAIL_SUBJECT_PARAMS_ERROR = 7  # 邮件主题参数格式错误
STATUS_MAIL_FROM_ADDRESS_NONE_ERROR = 8  # 邮件发送地址为空
STATUS_MAIL_FROM_ADDRESS_PARAMS_ERROR = 9  # 邮件发送地址参数格式错误
STATUS_MAIL_TO_ADDRESS_NONE_ERROR = 10  # 邮件目标地址为空
STATUS_MAIL_TO_ADDRESS_PARAMS_ERROR = 11  # 邮件目标地址参数格式错误
STATUS_MAIL_CONTENT_NONE_ERROR = 12  # 邮件内容为空
STATUS_MAIL_CONTENT_PARAMS_ERROR = 13  # 邮件内容参数错误
STATUS_MAIL_HELO_ERROR = 14  # 无法连接到邮件服务器
STATUS_MAIL_REJECTED_ALL_ERROR = 15  # 服务器拒绝所有接收方
STATUS_MAIL_SENDER_REFUSED_ERROR = 16  # 服务器拒绝发送地址请求
STATUS_MAIL_UNEXPECTED_CODE_ERROR = 17  # 服务器返回其他错代码

# 邮件默认配置
DEFAULT_SERVER = {
    'HOST': settings.MAIL_SERVER_HOST,
    'PORT': settings.MAIL_SERVER_PORT,
    'MAIL_FROM': settings.MAIL_SERVER_USER,
    'USERNAME': settings.MAIL_SERVER_USER,
    'PASSWORD': settings.MAIL_SERVER_PASSWORD
}


def send_instant_mail(
        mail_server: dict = DEFAULT_SERVER, mail_from: str = DEFAULT_SERVER['USERNAME'], mail_to: list = None, copy_to: list = [],
        subject: str = '提醒邮件', content: str = '', content_images: dict = None,
        attachments: list = None) -> int:
    """
    立即发送邮件
    :param mail_server: 邮件服务器
    :param mail_from: 发送邮箱
    :param mail_to: 接收邮箱
    :param subject: 邮件主题
    :param content: 内容
    :param content_images: 附件图片资源
    :param attachments: 邮件附件
    :return:
    """
    status = _check_mail_params(mail_server, mail_from, mail_to, subject, content)
    exception = None
    if status == STATUS_MAIL_SEND_SUCCEED:
        try:
            mail_mime = MIMEMultipart()
            # 邮件信息
            mail_to = list(set(mail_to))
            mail_mime['From'] = mail_from
            mail_mime['To'] = COMMASPACE.join(mail_to)
            mail_mime['Cc'] = COMMASPACE.join(copy_to)
            mail_mime['Subject'] = Header(subject, 'utf-8')
            mail_mime['Date'] = formatdate(localtime=True)
            # 邮件内容
            html_content = MIMEText(content, 'html', 'utf-8')
            mail_mime.attach(html_content)
            # 邮件内容图片
            if isinstance(content_images, dict):
                for content_id, image_path in content_images.items():
                    if image_path:
                        image = open(image_path, 'rb')
                        image_mime = MIMEImage(image.read())
                        image_mime.add_header('Content-ID', content_id)
                        image.close()
                        mail_mime.attach(image_mime)
            # 邮件附件
            if isinstance(attachments, list):
                for attachment in attachments:
                    a_mime = MIMEBase('application', 'octet-stream')
                    a_file = open(attachment, 'rb')
                    a_mime.set_payload(a_file.read())
                    # Base64加密成字符串
                    encoders.encode_base64(a_mime)
                    a_mime.add_header('Content-Disposition',
                                      'attachment', filename=("gbk", "", os.path.basename(attachment)))
                    mail_mime.attach(a_mime)
            try:
                smtp = smtplib.SMTP_SSL(mail_server['HOST'])
                smtp.ehlo()
                smtp.login(mail_server['USERNAME'], mail_server['PASSWORD'])
                smtp.sendmail(mail_from, mail_to, mail_mime.as_string())
            except smtplib.SMTPHeloError as she:
                status = STATUS_MAIL_HELO_ERROR
                raise she
            except smtplib.SMTPRecipientsRefused as srr:
                status = STATUS_MAIL_REJECTED_ALL_ERROR
                raise srr
            except smtplib.SMTPSenderRefused as ssr:
                status = STATUS_MAIL_SENDER_REFUSED_ERROR
                raise ssr
            except smtplib.SMTPDataError as sde:
                status = STATUS_MAIL_UNEXPECTED_CODE_ERROR
                raise sde
            smtp.close()
        except Exception:
            status = STATUS_MAIL_SEND_FAILED
            exception = traceback.format_exc()
        # 存储邮件历史
        try:
            instant_mail = InstantMail(
                mail_server=mail_server, mail_from=mail_from, mail_to=mail_to, status=status, subject=subject,
                content=content, exception=exception)
            if content_images:
                instant_mail.content_images = content_images
            if attachments:
                instant_mail.attachments = attachments
            instant_mail.exception = exception
            instant_mail.sync_save()
        except Exception:
            pass
    return status


def _check_mail_params(mail_server, mail_from, mail_to, subject, content):
    """
    邮件参数检查
    :param mail_server: 邮件服务器配置
    :param mail_from: 发送邮箱地址
    :param mail_to: 目标邮箱地址
    :param subject: 邮件主题
    :param content: 邮件内容
    :return:
    """
    if isinstance(mail_server, dict):
        if not mail_server.get('HOST'):
            return STATUS_MAIL_SERVER_HOST_ERROR
        elif not mail_server.get('USERNAME'):
            return STATUS_MAIL_SERVER_USERNAME_ERROR
        elif not mail_server.get('PASSWORD'):
            return STATUS_MAIL_SERVER_PASSWORD_ERROR
    else:
        return STATUS_MAIL_SERVER_ERROR

    if not subject:
        return STATUS_MAIL_SUBJECT_NONE_ERROR
    elif not isinstance(subject, (bytes, str)):
        return STATUS_MAIL_SUBJECT_PARAMS_ERROR

    if not mail_from:
        return STATUS_MAIL_FROM_ADDRESS_NONE_ERROR
    elif not isinstance(mail_from, (bytes, str)):
        return STATUS_MAIL_FROM_ADDRESS_PARAMS_ERROR

    if not mail_to:
        return STATUS_MAIL_TO_ADDRESS_NONE_ERROR
    elif not isinstance(mail_to, list):
        return STATUS_MAIL_TO_ADDRESS_PARAMS_ERROR

    if not content:
        return STATUS_MAIL_CONTENT_NONE_ERROR
    elif not isinstance(content, (bytes, str)):
        return STATUS_MAIL_CONTENT_PARAMS_ERROR

    return STATUS_MAIL_SEND_SUCCEED


if __name__ == '__main__':
    print(send_instant_mail(mail_to=['jian.zhou@idiaoyan.com'], copy_to=['jian.zhou@idiaoyan.com'],subject='提醒邮件11', content='这仅仅是一个测试！'))