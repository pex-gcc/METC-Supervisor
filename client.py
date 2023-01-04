from typing import List
from xmlrpc.client import Boolean

import requests
import json
import cosmosdb_helpers as db_help
import os
import validators
import re
import logging


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
        
def call_operators(call_info: dict) -> None:
    operators = get_operator(call_info.get('operator'))
            
    if len(operators) == 1:
        management_dial(call_info.get('destination_alias'), operators[0], call_info.get('operator', {}).get('display_name'))
     
    return
