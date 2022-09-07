from typing import Container, List
from xmlrpc.client import Boolean
from threading import Timer
from datetime import datetime, timedelta

import requests
import json
import cosmosdb_helpers as db_help
import os
import validators
import re
import logging
import azure.durable_functions as df


# class api_client:
#     def get_token(self, resp: requests.Response) -> None:
#         if resp.status_code == 200:
#             self.token = json.loads(resp.text)['result']['token']
#             self.ref = Timer(40.0, self.refresh)
#             self.ref.start()

#     def __init__(self, fqdn: str, conf: str, pin: str, name: str = "API") -> None:
#         self.url_base = f'{fqdn}/api/client/v2/conferences/{conf}'
#         body = {"display_name": name}
#         header = {"pin" : pin}
#         resp = requests.post(f'{self.url_base}/request_token', json=body, headers=header)
#         if resp.status_code == 200:
#             self.get_token(resp)
#             self.uuid = json.loads(resp.text)['result']['participant_uuid']
#             self.conference = conf

#     def __repr__(self) -> str:
#         return self.uuid
        
#     def refresh(self) -> None:
#         header = {"token" : self.token}
#         resp = requests.post(f'{self.url_base}/refresh_token', headers=header)
#         self.get_token(resp)

#     def release(self) -> None:
#         self.ref.cancel()
#         header = {"token" : self.token}
#         resp = requests.post(f'{self.url_base}/release_token', headers=header)

def get_fqdn(fqdn: str) -> str:
    prefix = r"^(https://|http://)?(.+)"
    match = re.search(prefix, fqdn)
    if not validators.domain(match.group(2)):
        return None
    if not match.group(1):
        fqdn = f'https://{fqdn}'
    return fqdn

def get_env(var: str) -> str:
    env = os.environ.get(var, None)
    if not env:
        logging.info(f'client.get_env: Missing ''{var}'' environment variable')
        raise Exception("Missing environment variable")
    return env

# Return the operator or multiple operators
def get_operator(oper: dict) -> List:
    events_db_name = get_env('EventsDatabaseName')
    activecalls_container_name = get_env('ActiveCallsContainerName')

    # Initialize events database
    db_events = db_help.db_init(events_db_name, activecalls_container_name, '/data/service_tag')
    
    #Get all participants in the operator conferences
    operators = {}
    query = f'SELECT * FROM {activecalls_container_name} c WHERE c.data.service_tag = "{oper.get("name")}"'
    operator_participants = db_help.db_query(db_events, query)
    
    # Make a dict of operator conferences with the number of participants in each
    for p in operator_participants:
        if not p.get('data', {}).get('conference') in operators:
            operators[p['data']['conference']] = 1
        else:
            operators[p['data']['conference']] += 1
    
    # If no operator conferences, return the base operator name
    if not operators:
        return []
    
    # If all operators are to be returned, return the keys.  Else find the first operator with the fewest participants
    if oper.get('dial_all', False):
        operator = list(operators.keys())
    else:
        operator = [k for k, v in operators.items() if v==min(operators.values())][:1]
        
    return operator

def management_dial(from_alias: str, to_alias: str, display_name: str) -> None:
        fqdn = get_fqdn(get_env('ManagementNodeFQDN'))
        uname = get_env('ManagementNodeUsername')
        pwd = get_env('ManagementNodePassword')
        dial_location = get_env('SIPDialLocation')
        dom = get_env('SIPDialingDomain')

        api_dial = f'/api/admin/command/v1/participant/dial/'
    
        if not fqdn:
            logging.info(f'client.py.management_dial: Invalid value for ManagementNodeFQDN')
            return

        data = {
            'conference_alias': from_alias,
            'destination': f'{to_alias}@{dom}',
            'routing': 'manual',
            'role': 'guest',
            'remote_display_name': display_name,
            'system_location': dial_location
        }
    
        requests.post(f'{fqdn}{api_dial}', auth=(uname, pwd), json=data)
        
async def call_operators(call_info: dict, client: df.DurableOrchestrationClient) -> None:
    operators = get_operator(call_info.get('operator'))
            
    if len(operators) == 1:
        management_dial(call_info.get('destination_alias'), operators[0], call_info.get('operator', {}).get('display_name'))

    elif operators:
        fqdn = get_fqdn(get_env('ConferenceNodeFQDN'))
        if not fqdn:
            logging.info(f'client.py.find_operator: Invalid value for ConferenceNodeFQDN')
            return

        events_db_name = get_env('EventsDatabaseName')
        apitoken_container_name = get_env('APITokenContainerName')

        # Initialize events database
        db_api = db_help.db_init(events_db_name, apitoken_container_name, '/operator')
        body = {'display_name': call_info.get('conference')}
        header = {'pin' : ''}
            
        for operator in operators:
            url_base = f'{fqdn}/api/client/v2/conferences/{operator}'
            client_info = {'fqdn' : fqdn, 'caller' : call_info.get('destination_alias'), 'pin' : '', 'operator' : operator, 'display_name' : call_info.get('operator', {}).get('display_name')}

            resp = requests.post(f'{url_base}/request_token', json=body, headers=header)
            if resp.status_code == 200:
                client_info['token'] = json.loads(resp.text).get('result', {}).get('token')
                client_info['id'] = json.loads(resp.text).get('result', {}).get('participant_uuid')
                client_info['next_update'] = datetime.strftime(datetime.now() + timedelta(seconds=40), '%Y-%m-%d %H:%M:%S.%f')
                client_info['instance_id'] = await client.start_new('APIClientOrchestrator', None, client_info)

                db_help.db_add(db_api, client_info)        
    return

def end_api(call_id: str, db_api: Container, client: df.DurableOrchestrationClient) -> None:
    logging.info(f'client.py.end_api: Deleting all API calls associated with call-id {call_id}')

    fqdn = get_fqdn(get_env('ConferenceNodeFQDN'))
    if not fqdn:
        logging.info(f'client.py.find_operator: Invalid value for ConferenceNodeFQDN')
        return

    apitoken_container_name = get_env('APITokenContainerName')

    # Initialize events database
    api_calls = db_help.db_query(db_api, f'SELECT * FROM {apitoken_container_name} c WHERE c.id = "{call_id}"')
    if api_calls:
        this_call = api_calls[0]
        operator = this_call.get('operator')
        caller = this_call.get('caller')
        management_dial(caller, operator, this_call.get('display_name', 'API'))
        calls = db_help.db_query(db_api, f'SELECT * FROM {apitoken_container_name} c WHERE c.caller = "{caller}"')

        for call in calls:
            url_base = f'{fqdn}/api/client/v2/conferences/{call.get("operator")}'
            header = {"token" : call.get('token')}
            resp = requests.post(f'{url_base}/release_token', headers=header)
            if resp.status_code == 200:
                client.terminate(call.get('instance_id'), "Call ended")
                db_help.db_delete(db_api, call)        
            
    return