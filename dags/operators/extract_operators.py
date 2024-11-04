import os
import re
import time
from airflow.models import Variable
import requests
from msal import ConfidentialClientApplication
import json
import pandas as pd
import threading


def _get_from_graph_api(endpoint, savefile_path):
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

    while url:
        response_from_graph_api = requests.get(
            url=url,
            headers={'Authorization': 'Bearer ' + token['access_token']})
        if response_from_graph_api.status_code != 200:
            raise ConnectionError(f"Request Status Code was {response_from_graph_api.status_code}, url was {url}")
        with open(savefile_path, 'a+') as save_file:
            save_file.write(json.dumps(response_from_graph_api.json()))
            save_file.write('\n')
        url = response_from_graph_api.json().get('@odata.nextLink', False)


def generic_extract(graph_endpoint, output_fp):
    # Handles cases, when needed file structure is not existent
    output_dir = os.path.dirname(output_fp)
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    _get_from_graph_api(
        endpoint=graph_endpoint,
        savefile_path=output_fp)


def generic_extract_from_dataframe_args(graph_endpoint, input_fp, output_fp_template, max_parallel=1):
    def threading_function(sem, **kwargs):
        with sem:
            generic_extract(**kwargs)
            time.sleep(1)

    def extraction_via_threads(function, semaphore_val, function_kwargs_list):
        try:
            semaphore = threading.Semaphore(value=semaphore_val)
            thread_list = [threading.Thread(target=function, args=[semaphore], kwargs=function_kwargs)
                           for function_kwargs in function_kwargs_list]
            for thread in thread_list:
                thread.has_errors = False
                thread.start()
            for thread in thread_list:
                thread.join()
        except Warning:
            raise RuntimeError

    # Actual function
    # Import col-names from graph_endpoint
    pattern = re.compile('{([^}]+)}')
    columns = re.findall(pattern, graph_endpoint)

    # Use Cols from graph_endpoint_template
    df = pd.read_csv(input_fp, usecols=columns)
    # Generating Endpoint URLs from row values
    df['graph_endpoint'] = ''
    df['graph_endpoint'] = df.apply(lambda row: graph_endpoint.format_map(row), axis=1)
    # Generating Save-Directories from row values
    df['output_fp'] = df.apply(lambda row: output_fp_template.format_map(row), axis=1)

    extraction_via_threads(
        function=threading_function,
        semaphore_val=max_parallel,
        function_kwargs_list=df[['graph_endpoint', 'output_fp']].to_dict(orient='records')
    )

# def extract_channels():
#    with open(Variable.get("LA_ETL_TMP_BASE_PATH") + 'json/channel_scope.json') as channel_scope:
#        group_ids = json.load(channel_scope).keys()
#        for group_id in group_ids:
#            _get_from_graph_api(
#                endpoint=f"/beta/groups/{group_id}/channels",
#                savefile_path=Variable.get("LA_ETL_TMP_BASE_PATH") + "json/channels.json")
#
#    group_ids = get_list_of_groups()
#    for group_id in group_ids:
#        _get_from_graph_api(endpoint=f"/beta/{group_id}/channels",
#                            savefile_path=Variable.get("LA_ETL_TMP_BASE_PATH") + "json/channels.json")
