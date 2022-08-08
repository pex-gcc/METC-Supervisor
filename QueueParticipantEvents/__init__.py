import logging
import json
import os
import requests
import re

import azure.functions as func
import cosmosdb_helpers as db_help

db_events = None
db_config = None

def main(msg: func.QueueMessage) -> None:
    global db_events
    global db_config
    
    def call_operator(event: dict, oper: dict) -> None:
        operators = {}
        query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + oper.get('reponse').get('service_tag') + '"'
        operator_participants = db_help.db_query(db_events, query)
        for p in operator_participants:
            if not p['data']['conference'] in operators:
                operators[p['data']['conference']] = 1
            else:
                operators[p['data']['conference']] += 1
        
        min_part = 1000
        operator = oper.get('basename') + '1'
        for o in operators.keys():
            if operators[o] < min_part:
                min_part = operators[o]
                operator = o
                
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
            'remote_display_name': c.get('OperatorDisplayName'),
            'system_location': dial_location
        }
        
        requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)

        return operator

    # Initialize "active calls" database    
    if db_events is None:
        db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')

    # Get call configuration
    if db_config is None:
        db_config = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ConfigContainerName'], '/response/result/service_tag')

    config = db_help.db_query(db_config, 'SELECT * FROM ControlConfig')

    # Get event json data from queue
    logging.info(f'Participant queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event_data =  msg.get_body()
    event = json.loads(event_data)
    event_type = event['event']
    event['id'] = event['data']['call_id']
    
    if event_type == 'participant_connected':
        logging.info(f'Event is type {event_type}, sending to active calls db')
        db_help.db_add(db_events, event)
        
        c = None
        for conf in config:
            if event.get('response').get('service_tag') == conf.get('response').get('service_tag'):
                c = conf
                break
            
        if c and c.get('type') == 'caller' and c.get('connectoperator') and event.get('call_direction') == 'in':
            oper_conf = None
            for conf in config:
                if c.get('operatorname') == conf.get('response').get('service_tag'):
                    call_operator(event, conf)
                    break

    elif event_type == 'participant_disconnected':
        logging.info(f'Event type is {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)
        