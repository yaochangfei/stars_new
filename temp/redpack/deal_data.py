#! /usr/bin/python


import json

from db.models import RedPacketBox
from logger import log_utils
from pymongo import ReadPreference
import pdb
logger = log_utils.get_logging('repair_box', 'repair_box.log')

NUM = 9


def filter_data(race_cid):
    """

    :param race_cid:
    :return:
    """

    with open('./box-%s.json' % race_cid, 'r') as f:
        box = set(json.load(f))

    with open('./history-%s.json' % race_cid, 'r') as f:
        history = set(json.load(f))

    with open('./repair-%s.json' % race_cid, 'r') as f:
        repair_list = json.load(f)

    box = box.difference(history)
    history = history.difference(box)

    box_dict = {}
    for b in box:
        _c, _m = b.split('-')
        m_list = box_dict.get(_c, [])
        m_list.append(_m)
        box_dict[_c] = m_list

    history_dict = {}
    for b in history:
        _c, _m = b.split('-')
        m_list = history_dict.get(_c, [])
        m_list.append(_m)
        history_dict[_c] = m_list

    print('box key:', len(box_dict))
    print('his key:', len(history_dict))
    for k, v in box_dict.items():
        print(k, len(v))
    print('-----------------------------')
    for k, v in history_dict.items():
        print(k, len(v))
    print('----------init finish--------')
    print('--------- repair start ------')
    fail_box = {}
    index = 0
    change_list = []
    for repair in repair_list:
        _box_cid, _member_cid, _checkpoint_cid = repair.split('-')
        _box = RedPacketBox.sync_find_one({'cid': _box_cid})
        try:
            _cid = history_dict[_checkpoint_cid].pop()

            while True:
                if RedPacketBox.sync_count({'race_cid': race_cid, 'member_cid': _cid},
                                           read_preference=ReadPreference.PRIMARY) < NUM:
                    break
                else:
                    _cid = history_dict[_checkpoint_cid].pop()
                    print(' --- skip ---')

            change_msg = '%s-%s-->%s-%s' % (_box.checkpoint_cid, _box.member_cid, _checkpoint_cid, _cid)
            logger.info(change_msg)
            _box.member_cid = _cid
            _box.needless['repair_flag'] = 1

            # _box.draw_dt =
            _box.sync_save()
            change_list.append(change_msg)
            index += 1
            print('has deal', index)
        except IndexError:
            _mm = fail_box.get(_checkpoint_cid, [])
            _mm.append(repair)
            fail_box[_checkpoint_cid] = _mm

    fail_box2 = {}
    new_his_map = []
    for c, m_list in history_dict.items():
        for m in m_list:
            new_his_map.append([m, c])

    for k, repair_list in fail_box.items():
        for repair in repair_list:
            pdb.set_trace()
            _box_cid, _member_cid, _checkpoint_cid = repair.split('-')
            _box = RedPacketBox.sync_find_one({'cid': _box_cid})
            try:
                member_cid, checkpoint_cid = new_his_map.pop()
                while True:
                    if RedPacketBox.sync_count({'race_cid': race_cid, 'member_cid': member_cid},
                                               read_preference=ReadPreference.PRIMARY) < NUM:
                        break
                    else:
                        member_cid, checkpoint_cid = new_his_map.pop()
                        print(' --- skip ---')

                change_msg = '%s-%s-->%s-%s' % (_box.checkpoint_cid, _box.member_cid, _checkpoint_cid, member_cid)
                logger.info(change_msg)

                _box.checkpoint_cid = checkpoint_cid
                _box.member_cid = member_cid
                _box.needless['repair_flag'] = 1

                # _box.draw_dt =
                _box.sync_save()
                change_list.append(change_msg)
                index += 1
                print('has deal', index)
            except IndexError:
                _mm = fail_box2.get(_checkpoint_cid, [])
                _mm.append(repair)
                fail_box2[_checkpoint_cid] = _mm

    assert fail_box2 == {}, 'fail box not empty'


if __name__ == '__main__':
    filter_data('DF1EDC30F120AEE93351A005DC97B5C1')  # ')F742E0C7CA5F7E175844478D74484C29
