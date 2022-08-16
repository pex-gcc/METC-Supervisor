from typing import List
from xmlrpc.client import Boolean
import requests
import json
import cosmosdb_helpers as db_help
import os

from threading import Timer

class api_client:
    def get_token(self, resp: requests.Response) -> None:
        if resp.status_code == 200:
            self.token = json.loads(resp.text)['result']['token']
            self.ref = Timer(40.0, self.refresh)
            self.ref.start()

    def __init__(self, fqdn: str, conf: str, pin: str, name: str = "API") -> None:
        self.url_base = "https://" + fqdn + "/api/client/v2/conferences/" + conf 
        body = {"display_name": name}
        header = {"pin" : pin}
        resp = requests.post(self.url_base + "/request_token", json=body, headers=header)
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


# Return the operator or multiple operators
# def get_operator(oper: dict, GetAll: Boolean = False) -> List:
#     # Initialize events database
#     db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')
    
#     #Get all participants in the operator conferences
#     operators = {}
#     query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + oper.get('response', {}).get('result', {}).get('service_tag') + '"'
#     operator_participants = db_help.db_query(db_events, query)
    
#     # Make a dict of operator conferences with the number of participants in each
#     for p in operator_participants:
#         if not p['data']['conference'] in operators:
#             operators[p['data']['conference']] = 1
#         else:
#             operators[p['data']['conference']] += 1
    
#     # If no operator conferences, return the base operator name
#     if not operators:
#         return [oper.get('basename') + '1']
    
#     # If all operators are to be returned, return the keys of the dict.  Else find the operators where the fewest participants are
#     if GetAll:
#         operator = list(operators.keys())
#     else:
#         operator = [k for k, v in operators.items() if v==min(operators.values())]
        
#     return operator

# Return the operator or multiple operators
def get_operator(oper: dict) -> List:
    # Initialize events database
    db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')
    
    #Get all participants in the operator conferences
    operators = {}
    query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + oper.get('name') + '"'
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
        
def call_operator(alias: str, oper: dict) -> None:
    operator = get_operator(oper)[0]
            
    fqdn = os.environ["ManagementNodeFQDN"]
    uname = os.environ["ManagementNodeUsername"]
    pwd = os.environ["ManagementNodePassword"]
    dial_location = os.environ["SIPDialLocation"]
    dom = os.environ["SIPDialingDomain"]

    api_dial = "/api/admin/command/v1/participant/dial/"
    
    data = {
        'conference_alias': alias,
        'destination': operator + '@' + dom,
        'routing': 'manual',
        'role': 'guest',
        'remote_display_name': oper.get('display_name'),
        'system_location': dial_location
    }
    
    requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)

def find_operator(alias: str, oper: dict) -> None:
    operator = get_operator(oper)
            
    fqdn = os.environ["ManagementNodeFQDN"]
    uname = os.environ["ManagementNodeUsername"]
    pwd = os.environ["ManagementNodePassword"]
    dial_location = os.environ["SIPDialLocation"]
    dom = os.environ["SIPDialingDomain"]

    api_dial = "/api/admin/command/v1/participant/dial/"
    
    data = {
        'conference_alias': alias,
        'destination': operator + '@' + dom,
        'routing': 'manual',
        'role': 'guest',
        'remote_display_name': oper.get('display_name'),
        'system_location': dial_location
    }
    
    if len(operator) == 1:
        requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)
