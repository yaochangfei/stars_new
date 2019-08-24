"""
应 @王华 要求：
第一步
把现在线上模块里面的数据从2019年3月29号开始全部挪到扫码模块里面
第二步
把现在这个线上二维码未来所有的数据全部归为扫码模块里面
第三步
重新给我开个二维码，这个二维码所有的数据放到线上这个包里面，接着2018年11月19以后



step1： create QR scene = 6
step2:  move online data(before 2019-03-29) to scene(6)
step3:  change statistics
"""
import traceback
from datetime import datetime

from db.models import Member

date_value = datetime.now().replace(year=2019, month=3, day=29, hour=0, minute=0, second=0, microsecond=0)
cursor = Member.sync_find({'source': 2, 'created_dt': {'$lte': date_value}})

while True:
    try:
        member = cursor.next()
        member.needless['old_source'] = member.source
        member.source = 6
        member.sync_save()
    except StopIteration:
        print(traceback.format_exc())
        break
