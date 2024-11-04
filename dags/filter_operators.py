import json

from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook


def get_user_ids_in_scope():
    connection = PostgresHook.get_hook(conn_id='la-db-production')
    with connection.get_cursor() as cursor:
        cursor.execute('SELECT user_id from teams_group_user WHERE member_end<now() or member_end is null;')
        user_ids = [row[0] for row in cursor.fetchall()]
    return user_ids


def filter_extracted_data(data_type):
    # load user_ids, if necessary
    if data_type == 'user':
        user_ids = get_user_ids_in_scope()

    data_type_map = {
        'group': {
            'filter_func': lambda group_name: group_name in json.loads(Variable.get('LA_GROUP_NAMES'))['groups'],
            'filter_criteria': 'displayName'
        },
        'user': {
            'filter_func': lambda user_id: user_id in user_ids,
            'filter_criteria': 'id'
        }
    }
    assert data_type in data_type_map, 'Data Type not implemented!'

    with open(Variable.get("LA_ETL_TMP_BASE_PATH") + f"json/{data_type}s.json") as source_file, \
            open(Variable.get("LA_ETL_TMP_BASE_PATH") + f"json/{data_type}s_filtered.json", 'a+') as target_file:
        for line in source_file.readlines():
            data = json.loads(line)
            filtered_data = [
                row for row in data if
                data_type_map[data_type]['filter_func'](row.get(data_type_map[data_type]['filter_criteria']))
            ]
            target_file.write(json.dumps(filtered_data))
            target_file.write('\n')


def remove_duplicates(source_fp, target_fp):
    with open(source_fp) as source, open(target_fp, 'w+') as target:
        data = []
        for line in source.readlines():
            line_data = json.loads(line)
            data += line_data
        data_without_duplicates = []
        for entry in data:
            if entry not in data_without_duplicates:
                data_without_duplicates.append(entry)
        target.write(json.dumps(data_without_duplicates))


def remove_arg(source_fp, target_fp, arg):
    with open(source_fp) as source, open(target_fp, 'w+') as target:
        data = []
        for line in source.readlines():
            line_data = json.loads(line[:-1])
            data += line_data
        for i in range(len(data)):
            data[i].pop(arg)
        target.write(json.dumps(data))
