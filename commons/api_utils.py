# !/usr/bin/python
# -*- coding:utf-8 -*-


def get_show_source_label(source):
    if len(source.label) > 0:
        label = source.label[0:3]
    else:
        label = []
    return label


def get_show_source_articulation(source):
    articulation = ''
    if len(source.download) > 0:
        d_name = source.download[0].get('downloadname', '')
        if d_name:
            d_name = d_name.upper()
            if '720' in d_name:
                articulation = '720P'
            elif '1080' in d_name:
                articulation = '1080P'
            elif '2K' in d_name:
                articulation = '2K'
            elif '4K' in d_name:
                articulation = '4K'
            elif 'BD' in d_name:
                articulation = 'BD'
            elif 'HD' in d_name:
                articulation = 'HD'
            elif 'TS' in d_name:
                articulation = 'TS'
    return articulation
