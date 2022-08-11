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

def get_operator(oper: dict, GetAll: Boolean = False) -> List:
    db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')
    
    operators = {}
    query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + oper.get('response', {}).get('result', {}).get('service_tag') + '"'
    operator_participants = db_help.db_query(db_events, query)
    for p in operator_participants:
        if not p['data']['conference'] in operators:
            operators[p['data']['conference']] = 1
        else:
            operators[p['data']['conference']] += 1
    
    if not operators:
        return oper.get('basename') + '1'
    
    if GetAll:
        operator = list(operators.keys())
    else:
        operator = [k for k, v in operators.items() if v==min(operators.values())]
        
    return operator
        
def call_operator(event: dict, oper: dict) -> None:
    # Initialize "active calls" database    
    # db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')
    
    # operators = {}
    # query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + oper.get('response', {}).get('result', {}).get('service_tag') + '"'
    # operator_participants = db_help.db_query(db_events, query)
    # for p in operator_participants:
    #     if not p['data']['conference'] in operators:
    #         operators[p['data']['conference']] = 1
    #     else:
    #         operators[p['data']['conference']] += 1
    
    
    
    # min_part = 1000
    # operator = oper.get('basename') + '1'
    # for o in operators.keys():
    #     if operators[o] < min_part:
    #         min_part = operators[o]
    #         operator = o

    operator = get_operator(oper)[0]
            
    fqdn = os.environ["ManagementNodeFQDN"]
    uname = os.environ["ManagementNodeUsername"]
    pwd = os.environ["ManagementNodePassword"]
    dial_location = os.environ["SIPDialLocation"]
    dom = oper.get('domain')

    api_dial = "/api/admin/command/v1/participant/dial/"
    
    data = {
        'conference_alias': event['data']['destination_alias'],
        'destination': operator + '@' + dom,
        'routing': 'manual',
        'role': 'guest',
        'remote_display_name': oper.get('display_name'),
        'system_location': dial_location
    }
    
    requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)
