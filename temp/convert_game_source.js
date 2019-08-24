#! /usr/bin/python



db.TBL_MEMBER.updateMany({'source': 1}, {'$set': {'source': '1'}});
db.TBL_MEMBER.updateMany({'source': 2}, {'$set': {'source': '2'}});
db.TBL_MEMBER.updateMany({'source': 3}, {'$set': {'source': '3'}});
db.TBL_MEMBER.updateMany({'source': 4}, {'$set': {'source': '4'}});
db.TBL_MEMBER.updateMany({'source': 5}, {'$set': {'source': '5'}});
db.TBL_MEMBER.updateMany({'source': 6}, {'$set': {'source': '6'}});
db.TBL_MEMBER.updateMany({'source': 99}, {'$set': {'source': '99'}});
