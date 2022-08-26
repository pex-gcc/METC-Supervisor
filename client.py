from typing import List
from xmlrpc.client import Boolean
import requests
import json
import cosmosdb_helpers as db_help
import os
import validators
import re
import logging

from threading import Timer

class api_client:
    def get_token(self, resp: requests.Response) -> None:
        if resp.status_code == 200:
            self.token = json.loads(resp.text)['result']['token']
            self.ref = Timer(40.0, self.refresh)
            self.ref.start()

    def __init__(self, fqdn: str, conf: str, pin: str, name: str = "API") -> None:
        self.url_base = f'{fqdn}/api/client/v2/conferences/{conf}'
        body = {"display_name": name}
        header = {"pin" : pin}
        resp = requests.post(f'{self.url_base}/request_token', json=body, headers=header)
        if resp.status_code == 200:
            self.get_token(resp)
            self.uuid = json.loads(resp.text)['result']['participant_uuid']
            self.conference = conf

    def __repr__(self) -> str:
        return self.uuid
        
    def refresh(self) -> None:
        header = {"token" : self.token}
        resp = requests.post(f'{self.url_base}/refresh_token', headers=header)
        self.get_token(resp)

    def release(self) -> None:
        self.ref.cancel()
        header = {"token" : self.token}
        resp = requests.post(f'{self.url_base}/release_token', headers=header)

def get_fqdn(fqdn: str) -> str:
    prefix = r"^(https://|http://)?(.+)"
    match = re.search(prefix, fqdn)
    if not validators.domain(match.group(2)):
        return None
    if not match.group(1):
        fqdn = f'https://{fqdn}'
    return fqdn

# Return the operator or multiple operators
def get_operator(oper: dict) -> List:
    events_db_name = os.environ.get('EventsDatabaseName', None)
    if not events_db_name:
        logging.info(f'PolicyServer: Missing config db name.  Check ''EventsDatabaseName'' environment variable')
        return

    activecalls_container_name = os.environ.get('ActiveCallsContainerName', None)
    if not activecalls_container_name:
        logging.info(f'PolicyServer: Missing config db name.  Check ''ActiveCallsContainerName'' environment variable')
        return

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
        fqdn = get_fqdn(os.environ.get('ManagementNodeFQDN'))
        uname = os.environ.get('ManagementNodeUsername')
        pwd = os.environ.get('ManagementNodePassword')
        dial_location = os.environ.get('SIPDialLocation')
        dom = os.environ.get('SIPDialingDomain')

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
        
def find_operator(alias: str, conference: str, oper: dict, api_clients: List) -> List:
    operators = get_operator(oper)
            
    if len(operators) == 1:
        management_dial(alias, operators[0], oper.get('display_name'))

    elif operators:
        fqdn = get_fqdn(os.environ.get('ConferenceNodeFQDN'))
        if not fqdn:
            logging.info(f'client.py.find_operator: Invalid value for ConferenceNodeFQDN')
            return api_clients
        
        for operator in operators:
            if alias in api_clients:
                api_clients[alias].append(api_client(fqdn, operator, '', conference))
            else:
                api_clients[alias] = [api_client(fqdn, operator, '', conference)]

    logging.info(f'client.py.find_operator: Number of existing API calls found after creation: {len(api_clients.keys())}')
        
    return api_clients

def end_api(call_id: str, api_clients: List) -> List:
    logging.info(f'client.py.end_api: Deleting all API calls associated with call-id {call_id}')
    logging.info(f'client.py.end_api: Number of existing API calls found: {len(api_clients.keys())}')

    for alias in api_clients.keys():
        if call_id in [a.uuid for a in api_clients[alias]]:
            logging.info(f'client.py.end_api: Accepted API call-id {call_id} found for conference {alias}')
            for client in api_clients[alias]:
                logging.info(f'client.py.end_api: Ending API call {client.uuid}')
                client.release()
            del api_clients[alias]
            
    return api_clients