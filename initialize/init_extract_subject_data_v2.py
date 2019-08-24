# !/usr/bin/python

from pymongo import ReadPreference

from db import STATUS_SUBJECT_CHOICE_RULE_ACTIVE
from db.models import SubjectChoiceRules
from tasks.instances.task_subject_extract import start_extract_subjects


def get_all_extract_rules(rule_code_list=None):
    if rule_code_list:
        return SubjectChoiceRules.sync_find(
            dict(status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE, code={'$in': rule_code_list}),
            read_preference=ReadPreference.PRIMARY).batch_size(32)

    return SubjectChoiceRules.sync_find(
        dict(status=STATUS_SUBJECT_CHOICE_RULE_ACTIVE), read_preference=ReadPreference.PRIMARY).batch_size(32)


def deal_with_extract_rules(rule_code_list=None):
    extract_rule_list = get_all_extract_rules(rule_code_list)
    if extract_rule_list:
        count = 1
        for extract_rule in extract_rule_list:
            if extract_rule:
                start_extract_subjects.delay(extract_rule)
                print(count, extract_rule.code, extract_rule.title)
                count += 1


if __name__ == '__main__':
    rule_codes = []
    deal_with_extract_rules(rule_code_list=rule_codes)
