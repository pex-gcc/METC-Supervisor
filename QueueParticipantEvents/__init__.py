import logging
import json
import os
import requests

import azure.functions as func
import cosmosdb_helpers as db_help

db_events = None

def main(msg: func.QueueMessage) -> None:
    global db_events
    
    def find_operator():
        operators = {}
        query = 'SELECT * FROM activeCalls c WHERE c.data.service_tag = "' + os.environ["OperatorServiceTag"] + '"'
        operator_participants = db_help.db_query(db_events, query)
        for p in operator_participants:
            if not p['data']['conference'] in operators:
                operators[p['data']['conference']] = 1
            else:
                operators[p['data']['conference']] += 1
        
        min_part = 1000
        operator = os.environ["OperatorConferenceBase"] + '1'
        for o in operators.keys():
            if operators[o] < min_part:
                min_part = operators[o]
                operator = o
                
        return operator

    # Initialize "active calls" database    
    if db_events is None:
        db_events = db_help.db_init('eventDatabase', 'activeCalls', '/data/service_tag')

    # Get event json data from queue
    logging.info(f'Participant queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event_data =  msg.get_body()
    event = json.loads(event_data)
    event_type = event['event']
    event['id'] = event['data']['call_id']
    
    if event_type == 'participant_connected':
        logging.info(f'Event is type {event_type}, sending to active calls db')
        db_help.db_add(db_events, event)
        
        if event['data']['service_tag'] == os.environ["CallerServiceTag"] and event['data']['call_direction'] == 'in':
            operator = find_operator()
            
            fqdn = os.environ["ManagementNodeFQDN"]
            uname = os.environ["ManagementNodeUsername"]
            pwd = os.environ["ManagementNodePassword"]
            dom = os.environ["SIPDialingDomain"]
            dial_location = os.environ["SIPDialLocation"]
            api_dial = "/api/admin/command/v1/participant/dial/"
            
            data = {
                'conference_alias': event['data']['destination_alias'],
                'destination': operator + '@' + dom,
                'routing': 'manual',
                'role': 'guest',
                'remote_display_name': os.environ["OperatorDisplayName"],
                'system_location': dial_location
            }
            
            requests.post(fqdn + api_dial, auth=(uname, pwd), json=data)

    elif event_type == 'participant_disconnected':
        logging.info(f'Event type is {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)
        