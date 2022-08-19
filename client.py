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

api_clients = {}

class api_client:
    def get_token(self, resp: requests.Response) -> None:
        if resp.status_code == 200:
            self.token = json.loads(resp.text)['result']['token']
            self.ref = Timer(40.0, self.refresh)
            self.ref.start()

    def __init__(self, fqdn: str, conf: str, pin: str, name: str = "API") -> None:
        self.url_base = fqdn + "/api/client/v2/conferences/" + conf 
        body = {"display_name": name}
        header = {"pin" : pin}
        resp = requests.post(self.url_base + "/request_token", json=body, headers=header)
        if resp.status_code == 200:
            self.get_token(resp)
            self.uuid = json.loads(resp.text)['result']['participant_uuid']
            self.conference = conf

    def __repr__(self) -> str:
        return self.uuid
        
    def refresh(self) -> None:
        header = {"token" : self.token}
        resp = requests.post(self.url_base + "/refresh_token", headers=header)
        self.get_token(resp)

    def release(self) -> None:
        self.ref.cancel()
        header = {"token" : self.token}
        resp = requests.post(self.url_base + "/release_token", headers=header)

def get_fqdn(fqdn: str) -> str:
    prefix = r"^(https://|http://)?(.+)"
    match = re.search(prefix, fqdn)
    if not validators.domain(match.group(2)):
        return None
    if not match.group(1):
        fqdn = 'https://' + fqdn
    return fqdn

# Return the operator or multiple operators
def get_operator(oper: dict) -> List:
    # Initialize events database
    db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')
    
    #Get all participants in the operator conferences
    operators = {}
    query = 'SELECT * FROM ' + os.environ['ActiveCallsContainerName'] + ' c WHERE c.data.service_tag = "' + oper.get('name') + '"'
    operator_participants = db_help.db_query(db_events, query)
    
    # Make a dict of operator conferences with the number of participants in each
    for p in operator_participants:
        if not p['data']['conference'] in operators:
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
        fqdn = get_fqdn(os.environ["ManagementNodeFQDN"])
        uname = os.environ["ManagementNodeUsername"]
        pwd = os.environ["ManagementNodePassword"]
        dial_location = os.environ["SIPDialLocation"]
        dom = os.environ["SIPDialingDomain"]

        api_dial = "/api/admin/command/v1/participant/dial/"
    
        if not fqdn:
            logging.info(f'Invalid value for ManagementNodeFQDN')
            return

        data = {
            'conference_alias': from_alias,
            'destination': to_alias + '@' + dom,
            'routing': 'manual',
            'role': 'guest',
            'remote_display_name': display_name,
            'system_location': dial_location
        }
    
        requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)
        
def find_operator(alias: str, conference: str, oper: dict) -> None:
    global api_clients

    operators = get_operator(oper)
            
    if len(operators) == 1:
        management_dial(alias, operators[0], oper.get('display_name'))

    elif operators:
        fqdn = get_fqdn(os.environ["ConferenceNodeFQDN"])
        if not fqdn:
            logging.info(f'Invalid value for ConferenceNodeFQDN')
            return
        
        for operator in operators:
            if alias in api_clients:
                api_clients[alias].append(api_client(fqdn, operator, '', conference))
            else:
                api_clients[alias] = [api_client(fqdn, operator, '', conference)]
                
def end_api(call_id: str) -> None:
    global api_clients

    for alias in api_clients.keys():
        if call_id in [a.uuid for a in api_clients[alias]]:
            for client in api_clients[alias]:
                client.release()
            del api_clients[alias]