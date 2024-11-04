import json
import re

from airflow.decorators import dag, task
import pendulum
import redis
import pandas as pd
import itertools

from airflow.models import Variable
from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import insert

from operators.custom_operators import get, load
from operators.load_operators import load_df_to_db


@dag(
	'learning-analytics-2.0',
	schedule_interval=None,
	start_date=pendulum.datetime(2022, 4, 4, 15, tz="Europe/Berlin"),
	tags=['test']
)
def learning_analytics_dag():
	@task()
	def extract_groups():
		r = redis.Redis()
		try:
			groups = get('/beta/groups')
			r.set('groups', json.dumps(groups))
		finally:
			r.close()
		return 'groups'

	@task()
	def transform_groups():
		r = redis.Redis()
		try:
			# Extract Groups from stored requests in redis
			groups = [row['value'] for row in json.loads(r.get('groups'))['values']]
			# Flatten list of entries
			df = pd.DataFrame(itertools.chain(*groups))
			# Rename columns to match db pattern
			df.columns = [re.sub(r'(?<!^)(?=[A-Z])', '_', col).lower() for col in df.columns]
			# Filter columns and rows
			df = df[['id', 'display_name', 'description', 'created_date_time']]
			group_names = json.loads(Variable.get('LA_GROUP_NAMES'))['display_name']
			df = df[df['display_name'].isin(group_names)]
			r.set('transformed_groups', df.to_json())
		finally:
			r.close()

	@task()
	def load_groups():
		r = redis.Redis()
		try:
			df = pd.read_json(r.get('transformed_groups'))
			index_columns = ['id']
			load(db_table='teams_group', dataframe=df, index_columns=index_columns, update_columns=[
				col for col in df.columns if col not in index_columns])
		finally:
			r.close()

	@task()
	def extract_group_users():
		r = redis.Redis()
		try:
			group_ids = list(pd.read_json(r.get('transformed_groups'))['id'])
			group_users = []
			for group_id in group_ids:
				group_users.append(get(f'/beta/teams/{group_id}/members'))
			r.set('group_users', json.dumps(group_users))
		finally:
			r.close()

	@task()
	def transform_group_users():
		r = redis.Redis()
		try:
			group_users = itertools.chain(*[row['values'] for row in json.loads(r.get('group_users'))])
			values = []
			for bulk in group_users:
				# extract group_id from metadata
				group_id = bulk['@odata.context'].split('/')[4].split("'")[-2]
				for entry in bulk['value']:
					entry['group_id'] = group_id
					values.append(entry)
			df = pd.DataFrame(values)
			# CamelCase to snake_case
			df.columns = [re.sub(r'(?<!^)(?=[A-Z])', '_', col).lower().replace('date_time', 'datetime') for col in
						  df.columns]
			df = df[['group_id', 'user_id']]
			r.set('transformed_group_users', df.to_json())
		finally:
			r.close()

	@task()
	def load_group_users():
		r = redis.Redis()
		try:
			df = pd.read_json(r.get('transformed_group_users'))
			load(db_table='teams_group_user', dataframe=df)
		finally:
			r.close()

	@task()
	def extract_team_channels():
		r = redis.Redis()
		try:
			group_ids = list(pd.read_json(r.get('transformed_groups'))['id'])
			teams_channels = []
			for group_id in group_ids:
				teams_channels.append(get(f'/beta/teams/{group_id}/channels'))
			r.set('teams_channels', json.dumps(teams_channels))
		finally:
			r.close()

	@task()
	def clean_redis():
		r = redis.Redis()
		try:
			for key in r.keys():
				r.delete(key)
		finally:
			r.close()

	@task()
	def task_template():
		r = redis.Redis()
		try:
			pass
		finally:
			r.close()

	extracted_groups = extract_groups()
	transformed_groups = transform_groups()
	loaded_groups = load_groups()
	extracted_group_users = extract_group_users()
	transformed_group_users = transform_group_users()
	loaded_group_users = load_group_users()
	extracted_teams_channels = extract_team_channels()
	# cleaned_redis = clean_redis()

	extracted_groups >> transformed_groups >> loaded_groups # >> cleaned_redis
	transformed_groups >> extracted_group_users >> transformed_group_users >> loaded_group_users #
	transformed_groups >> extracted_teams_channels


la_daf = learning_analytics_dag()