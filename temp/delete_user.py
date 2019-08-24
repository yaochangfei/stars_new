#! /usr/bin/python


from db.models import Member
from caches.redis_utils import RedisCache


if __name__ == '__main__':
    member = Member.sync_find_one({'nick_name': 'shuaixu'})
    RedisCache.delete(member.open_id)

    member.sync_delete()