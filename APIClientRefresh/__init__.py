# This function is not intended to be invoked directly. Instead it will be
# triggered by an orchestrator function.
# Before running this sample, please:
# - create a Durable orchestration function
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

import logging
import cosmosdb_helpers as db_help
from client import get_env
import requests
import json

def main(CallInfo: dict) -> dict:
    if CallInfo:
        events_db_name = get_env('EventsDatabaseName')
        apitoken_container_name = get_env('APITokenContainerName')

        # Initialize events database
        db_api = db_help.db_init(events_db_name, apitoken_container_name, '/operator')
        call = db_help.db_query(db_api, f'SELECT * FROM {apitoken_container_name} c WHERE c.id = "{CallInfo.get("id")}"')[0]

        header = {"token" : CallInfo.get('token')}
        url_base = f'{CallInfo.get("fqdn")}/api/client/v2/conferences/{CallInfo.get("operator")}'
        resp = requests.post(f'{url_base}/refresh_token', headers=header)
        if resp.status_code == 200:
            CallInfo['token'] = json.loads(resp.text).get('result', {}).get('token')
            db_api.replace_item(item=call, body=CallInfo)

        return CallInfo
