/*
学习效果
学习日正确率检测脚本

 */

db.TBL_MEMBER_GAME_HISTORY.aggregate([
    {
        $project: {
            daily_code: {
                $dateToString: { format: '%Y%m%d', date: '$created_dt' }
            },
            member_cid: 1,
            result: 1,
            correct: { $size: { $filter: { input: '$result.true_answer', as: 'item', cond: { $and: [{ '$eq': ['$$item', true] }] } } } },//{}
            total: { $size: '$result.true_answer' },//{}
        }
    }, {
        $group: {
            _id: {
                daily_code: '$daily_code',
                member_cid: '$member_cid'
            },
            correct: {
                $sum: '$correct'
            },
            total: {
                $sum: '$total'
            }
        }
    }, {
        $group: {
            _id: '$_id.member_cid',
            day: {
                $sum: 1
            },
            correct: {
                $sum: '$correct'
            },
            total: {
                $sum: '$total'
            }
        }
    }, {
        $group: {
            _id: '$day',
            correct: {
                $sum: '$correct'
            },
            total: {
                $sum: '$total'
            }
        }
    }, {
        $sort: {
            '_id': 1
        }
    }, {
        $project: {
            correct: {
                $sum: '$correct'
            },
            total: {
                $sum: '$total'
            },
            'ratio': {$divide: ['$correct', '$total']}
        }
    }
])