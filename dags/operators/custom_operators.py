import json
import requests
from airflow.models import Variable
from msal import ConfidentialClientApplication
from airflow.providers.postgres.hooks.postgres import PostgresHook
from sqlalchemy import MetaData
from sqlalchemy.dialects.postgresql import insert
from pandas import notnull


def get(endpoint):
	# Create_APP
	app = ConfidentialClientApplication(
		Variable.get("MICROSOFT_GRAPH_CLIENT_ID"),
		authority=Variable.get("MICROSOFT_GRAPH_CLIENT_AUTHORITY"),
		client_credential=Variable.get("MICROSOFT_GRAPH_CLIENT_SECRET"))
	url = Variable.get("MICROSOFT_GRAPH_BASE") + endpoint
	scope = Variable.get("MICROSOFT_GRAPH_SCOPE")

	# check for cached token
	token = app.acquire_token_silent([scope], account=None)

	if not token:
		# If no cached token exists, acquire new one
		token = app.acquire_token_for_client(scopes=['https://graph.microsoft.com/.default'])

	if "access_token" not in token:
		print(token)
		raise AssertionError("Microsoft Graph Access Token could not be acquired")

	responses = []

	while url:
		res = requests.get(url=url, headers={'Authorization': 'Bearer ' + token['access_token']})
		if res.status_code != 200:
			raise ConnectionError(f"Request Status Code was {res.status_code}, url was {url}")
		responses.append(res.json())
		url = res.json().get('@odata.nextLink', False)
	return responses


def load(db_table, dataframe, index_columns=None, update_columns=None):
	""" Loads Dataframe from csv to database table derived from connection id"""
	# Get Engine, derive Metadata from SQL
	connection = PostgresHook.get_hook(conn_id='la_db_teams_aj')
	engine = connection.get_sqlalchemy_engine()
	meta_data = MetaData(bind=engine, reflect=True)
	# Replace NaN with None
	dataframe = dataframe.where(notnull(dataframe), None)
	dataframe = dataframe.drop_duplicates(subset=index_columns)
	# Create SQL-Statement
	statement = insert(meta_data.tables[db_table], dataframe.to_dict('records'))
	if update_columns:
		statement = statement.on_conflict_do_update(
			index_elements={entry: statement.excluded[entry] for entry in index_columns},
			set_={entry: statement.excluded[entry] for entry in update_columns})
	else:
		statement = statement.on_conflict_do_nothing()
	# Execute SQL-Query
	engine.execute(statement)
