#! /usr/bin/python


from db import STATUS_RESULT_CHECK_POINT_WIN
from db.models import RedPacketBox, MemberCheckPointHistory
from pymongo import ReadPreference


def do_repair():
    cursor = RedPacketBox.sync_find({'needless.repair_flag': 1, 'draw_status': 0},
                                    read_preference=ReadPreference.PRIMARY).batch_size(128)
    for index, data in enumerate(cursor):
        history = MemberCheckPointHistory.sync_find_one(
            {'check_point_cid': data.checkpoint_cid, 'member_cid': data.member_cid,
             'status': STATUS_RESULT_CHECK_POINT_WIN})
        if not history:
            print('-- miss --', index, data.cid)
            continue
        data.draw_dt = history.created_dt
        data.sync_save()
        print('-- success --', index)


if __name__ == '__main__':
    do_repair()
