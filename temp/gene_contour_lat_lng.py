#! /usr/bin/python

import json

lat_list = []
with open('./division.json', 'r') as f:
    data = json.load(f)
    data = data['division']
    for prov in data:
        city_list = prov.get('cell', [])
        for city in city_list:
            lat_list.append(
                [city.get('name'), city.get('location').get('lng'), city.get('location').get('lat'),
                 prov.get('name').replace('省', '').replace('市', '')])

            dist_list = city.get('cell', '')
            for dist in dist_list:
                lat_list.append(
                    [dist.get('name'), dist.get('location').get('lng'),
                     dist.get('location').get('lat'),
                     city.get('name').replace('市', '')])

with open('./china_city.json', 'w', encoding='utf-8') as f:
    dist_list = json.dumps(lat_list, ensure_ascii=False)
    f.write(dist_list)
