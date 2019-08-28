# !/usr/bin/python
# -*- coding:utf-8 -*-

# 引入模块
from obs import ObsClient
import calendar, time
import datetime

ACCESS_KEY_ID = 'EOKVJSN4CMZ6DGNRESMN'
SECRET_ACCESS_KEY = '2qiY4bnPCLVHaPsQrbcudV8Ccg2slDah806SGESL'
SERVER = 'obs.cn-east-3.myhuaweicloud.com'
BUCKET_NAME = 'obs-63c3'

# 创建ObsClient实例
obsClient = ObsClient(
    access_key_id=ACCESS_KEY_ID,
    secret_access_key=SECRET_ACCESS_KEY,
    server=SERVER
)


# 上传文件流
def upload_file_to_obs(file, file_name):
    # resp = obsClient.putContent(BUCKET_NAME, '文本', content='Hello OBS')
    # content = open('/Users/yaochangfei/Downloads/%s' % file_name, 'rb')
    content = file.body
    file_name = str(calendar.timegm(time.gmtime())) + '_' + file_name
    # print(content)
    # print(type(content))
    # print(datetime.datetime.now())
    resp = obsClient.putContent(BUCKET_NAME, file_name, content=content)
    # print(datetime.datetime.now())
    print(resp)
    # if resp.status < 300:
    #     print('requestId:', resp.requestId)
    #     print('objectUrl',resp.body.objectUrl)
    # else:
    #     print('errorCode:', resp.errorCode)
    #     print('errorMessage:', resp.errorMessage)
    return resp


if __name__ == '__main__':
    print(datetime.datetime.now())
    file = '/Users/yaochangfei/Downloads/bg.jpg'
    upload_file_to_obs(file, 'bg.jpg')
    print(datetime.datetime.now())
