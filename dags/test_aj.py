from datetime import timedelta
from airflow import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator
from airflow.utils.dates import days_ago
from operators import extract_operators, transform_operators, load_operators, clean_operators

default_args = {
    'owner': 'volkmann',
    'depends_on_past': False,
    'email': ['nick.volkmann@tu-dresden.de'],
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

base_path = Variable.get('LA_ETL_TMP_BASE_PATH')

# Defining DAG-Metadata
dag = DAG(
    'la_test',
    default_args=default_args,
    description='This dag extracts all teams_data to the learning analytics database',
    schedule_interval='0 3 * * *',
    start_date=days_ago(1),
    max_active_runs=1,
    tags=['production', 'learning-analytics'],
    template_searchpath=base_path
)

extract_groups = PythonOperator(
    task_id='extract_teams_groups',
    python_callable=extract_operators.generic_extract,
    op_kwargs={
        'graph_endpoint': '/beta/groups',
        'output_fp': base_path + 'json/groups.json'
    },
    dag=dag,
)

transform_groups = PythonOperator(
    task_id='transform_teams_groups',
    python_callable=transform_operators.transform_json_to_df,
    op_kwargs={
        'input_fp': extract_groups.op_kwargs['output_fp'],
        'output_fp': base_path + "csv/groups.csv",
        'col_mapping': {
            'id': 'id',
            'displayName': 'display_name',
            'description': 'description',
            'createdDateTime': 'created_date_time'
        }
    },
)

filter_groups = PythonOperator(
    task_id='filter_groups',
    python_callable=transform_operators.filter_from_dict_string,
    op_kwargs={
        'input_fp': transform_groups.op_kwargs['output_fp'],
        'output_fp': transform_groups.op_kwargs['output_fp'],
        'dictionary': Variable.get('LA_GROUP_NAMES')
    }
)

load_groups = PythonOperator(
    task_id='load_groups',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'dataframe_fp': filter_groups.op_kwargs['output_fp'],
        'db_table': 'teams_group',
        'index_elements': ['id'],
        'upsert_cols': ['display_name', 'description', 'created_date_time']
    }
)

extract_group_users = PythonOperator(
    task_id='extract_group_users',
    python_callable=extract_operators.generic_extract_from_dataframe_args,
    op_kwargs={
        'graph_endpoint': '/beta/teams/{id}/members',
        'input_fp': transform_groups.op_kwargs['output_fp'],
        'output_fp_template': base_path + 'json/teams_group_users/{id}.json',
        'max_parallel': 1
    }
)

transform_group_users = PythonOperator(
    task_id='transform_group_users',
    python_callable=transform_operators.transform_json_to_df_for_each_in_directory,
    op_kwargs={
        'input_dir': base_path + 'json/teams_group_users',
        'output_dir': base_path + 'csv/teams_group_users',
        'col_mapping': {'userId': 'user_id'}
    }
)

merge_group_users = PythonOperator(
    task_id='merge_group_user_lists',
    python_callable=transform_operators.merge_dataframes_from_directory,
    op_kwargs={
        'input_dir_template': base_path + 'csv/teams_group_users/{group_id}.csv',
        'output_fp': base_path + 'csv/teams_group_users.csv'
    }
)

load_group_users = PythonOperator(
    task_id='load_group_users',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'dataframe_fp': merge_group_users.op_kwargs['output_fp'],
        'db_table': 'teams_group_user',
        'index_elements': ['user_id', 'group_id']
    }
)

extract_users = PythonOperator(
    task_id='extract_users',
    python_callable=extract_operators.generic_extract_from_dataframe_args,
    op_kwargs={
        'graph_endpoint': '/beta/users/{user_id}'
                          '?$select=id,displayName,givenName,surname,mail,preferred_language,userPrincipalName',
        'input_fp': merge_group_users.op_kwargs['output_fp'],
        'output_fp_template': base_path + 'json/teams_users/{user_id}.json',
        'max_parallel': 1
    }
)

transform_users = PythonOperator(
    task_id='transform_users',
    python_callable=transform_operators.transform_json_to_df_for_each_in_directory,
    op_kwargs={
        'input_dir': base_path + 'json/teams_users',
        'output_dir': base_path + 'csv/teams_users',
        'value_nested': False,
        'col_mapping': {
            'displayName': 'display_name',
            'givenName': 'given_name',
            'surname': 'surname',
            'mail': 'mail'
        }
    }
)

transform_user_principal_names = PythonOperator(
    task_id='transform_user_principal_names',
    python_callable=transform_operators.transform_json_to_df_for_each_in_directory,
    op_kwargs={
        'input_dir': base_path + 'json/teams_users',
        'output_dir': base_path + 'csv/teams_user_principal_names',
        'value_nested': False,
        'col_mapping': {
            'userPrincipalName': 'user_principal_name',
        }
    }
)

merge_users = PythonOperator(
    task_id='merge_user_lists',
    python_callable=transform_operators.merge_dataframes_from_directory,
    op_kwargs={
        'input_dir_template': base_path + 'csv/teams_users/{id}.csv',
        'output_fp': base_path + 'csv/teams_users.csv',
    }
)

merge_user_principal_names = PythonOperator(
    task_id='merge_user_principal_name_list',
    python_callable=transform_operators.merge_dataframes_from_directory,
    op_kwargs={
        'input_dir_template': base_path + 'csv/teams_user_principal_names/{teams_user_id}.csv',
        'output_fp': base_path + 'csv/teams_user_principal_names.csv',
    }
)

load_user_principal_names = PythonOperator(
    task_id='load_user_principal_names',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'dataframe_fp': merge_user_principal_names.op_kwargs['output_fp'],
        'db_table': 'ms365_user_principal_name',
        'index_elements': ['teams_user_id', 'user_principal_name'],
    }
)

load_users = PythonOperator(
    task_id='load_users',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'dataframe_fp': merge_users.op_kwargs['output_fp'],
        'db_table': 'teams_user',
        'index_elements': ['id'],
        'upsert_cols': ['display_name', 'given_name', 'surname', 'mail', 'preferred_language']
    }
)

extract_channels = PythonOperator(
    task_id='extract_channels',
    python_callable=extract_operators.generic_extract_from_dataframe_args,
    op_kwargs={
        'graph_endpoint': '/beta/teams/{id}/channels',
        'input_fp': filter_groups.op_kwargs['output_fp'],
        'output_fp_template': base_path + 'json/teams_channels/{id}.json',
        'max_parallel': 1
    }
)

transform_channels = PythonOperator(
    task_id='transform_channels',
    python_callable=transform_operators.transform_json_to_df_for_each_in_directory,
    op_kwargs={
        'input_dir': base_path + 'json/teams_channels',
        'output_dir': base_path + 'csv/teams_channels',
        'col_mapping': {
            'id': 'id',
            'displayName': 'display_name',
            'createdDateTime': 'created_date_time',
            'description': 'description',
            'membershipType': 'membership_type',
            'webUrl': 'web_url'
        },
    }
)

merge_channels = PythonOperator(
    task_id='merge_channels',
    python_callable=transform_operators.merge_dataframes_from_directory,
    op_kwargs={
        'input_dir_template': base_path + 'csv/teams_channels/{group_id}.csv',
        'output_fp': base_path + 'csv/teams_channels.csv'
    }
)

load_channels = PythonOperator(
    task_id='load_channels',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'db_table': 'teams_channel',
        'dataframe_fp': merge_channels.op_kwargs['output_fp'],
        'index_elements': ['id'],
        'upsert_cols': [
            'group_id', 'display_name', 'description', 'membership_type', 'web_url', 'moderation_settings']
    }
)

extract_channel_messages = PythonOperator(
     task_id='extract_channel_messages',
     python_callable=extract_operators.generic_extract_from_dataframe_args,
     op_kwargs={
         'graph_endpoint': '/beta/teams/{group_id}/channels/{id}/messages',
         'input_fp': merge_channels.op_kwargs['output_fp'],
         'output_fp_template': base_path + 'json/channel_messages/{group_id}/{id}.json',
         'max_parallel': 1
     }
 )

#extract_channel_messages = PythonOperator(
#    task_id='extract_channel_messages',
#    python_callable=extract_operators.generic_extract_from_dataframe_args,
#    op_kwargs={
#        'graph_endpoint': '/beta/teams/{group_id}/channels/getAllMessages',
#        'input_fp': merge_channels.op_kwargs['output_fp'],
#        'output_fp_template': base_path + 'json/channel_messages/{group_id}/all_messages.json',
#        'max_parallel': 1
#    }
#)

transform_channel_messages = PythonOperator(
    task_id='transform_channel_messages',
    python_callable=transform_operators.transform_json_to_df_for_each_in_directory,
    op_kwargs={
        'input_dir': base_path + 'json/channel_messages',
        'output_dir': base_path + 'csv/channel_messages',
        'col_mapping': {
            'id': 'id',
            'messageType': 'message_type',
            'createdDateTime': 'created_date_time',
            'lastModifiedDateTime': 'last_modified_date_time',
            'lastEditedDateTime': 'last_edited_date_time',
            'deletedDateTime': 'deleted_date_time',
            'subject': 'subject',
            'summary': 'summary',
            'channelIdentity.channelId': 'channel_id',
            'importance': 'importance',
            'webUrl': 'web_url',
            'from.user.id': 'from_user_id',
            'channelIdentity.channelId': 'channel_id',
            'body.contentType': 'body_content_type',
            'body.content': 'body_content',
            # TODO: find solution:
            #  Attachments are in a sub-list and therfore ommitted by pd.normalize_json
            #  'attachmentID': 'attachment_id',
        },
    }
)

merge_channel_messages = PythonOperator(
    task_id='merge_channel_messages',
    python_callable=transform_operators.merge_dataframes_from_directory,
    op_kwargs={
        'input_dir_template': base_path + 'csv/channel_messages/{group_id}/{channel_id}.csv',
        'output_fp': base_path + 'csv/channel_messages.csv'
    }
)

load_channel_messages = PythonOperator(
    task_id='load_channel_messages',
    python_callable=load_operators.load_df_to_db,
    op_kwargs={
        'conn_id': 'la-db-production',
        'dataframe_fp': base_path + 'csv/channel_messages.csv',
        'db_table': 'teams_channel_message',
        'index_elements': ['id'],
        'upsert_cols': [
            'group_id', 'message_type', 'created_date_time', 'last_modified_date_time',
            'last_edited_date_time', 'deleted_date_time', 'subject', 'summary',
            'channel_id', 'importance', 'web_url', 'from_user_id', 'body_content_type',
            'body_content', 'attachment_id'
        ]
    }
)
#  extract_channel_message_reaction = PythonOperator()
#  transform_channel_message_reaction = PythonOperator()
#  merge_channel_message_reactions = PythonOperator()
#  load_channel_message_reactions = PythonOperator()

clean_up = PythonOperator(
    task_id='clean_up',
    python_callable=clean_operators.clean,
    op_kwargs={'file_path_or_dir': base_path},
    trigger_rule='all_success'
)

extract_groups >> transform_groups >> filter_groups >> load_groups >> clean_up
filter_groups >> extract_group_users >> transform_group_users >> merge_group_users >> load_group_users >> clean_up
merge_group_users >> extract_users >> transform_users >> merge_users >> load_users >> clean_up
extract_users >> transform_user_principal_names >> merge_user_principal_names >> load_user_principal_names >> clean_up
filter_groups >> extract_channels >> transform_channels >> merge_channels >> load_channels >> clean_up
merge_channels >> extract_channel_messages >> transform_channel_messages >> merge_channel_messages
merge_channel_messages >> load_channel_messages >> clean_up
#  merge_channel_messages >> extract_channel_message_reactions >> transform_channel_message_reactions
#  transform_channel_message_reactions >> merge_channel_message_reactions >> load_channel_message_reactions