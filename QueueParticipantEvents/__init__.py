import logging
import json
import os
import re

import azure.functions as func
import cosmosdb_helpers as db_help
from client import find_operator

def main(msg: func.QueueMessage) -> None:
    # Initialize "active calls" database    
    db_events = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ActiveCallsContainerName'], '/data/service_tag')

    # Get call configuration
    db_config = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ConfigContainerName'], '/response/result/service_tag')
    config = db_help.db_query(db_config, 'SELECT * FROM ControlConfig')

    # Initialize "API calls" database
    db_api = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['APICallsContainerName'], '/response/result/service_tag')

    # Get event json data from queue
    logging.info(f'Participant queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event_data =  msg.get_body()
    event = json.loads(event_data)
    event_type = event['event']
    event['id'] = event['data']['call_id']
    
    if event_type == 'participant_connected':
        logging.info(f'Event is type {event_type}, sending to active calls db')
        db_help.db_add(db_events, event)
        
        alias = event.get('data', {}).get('destination_alias')
        if alias:
            conf = None
            for c in config:
                match = re.match(c['alias'], alias)
                if match:
                    conf = c
                    break

            if conf and conf.get('operator') and event.get('data', {}).get('call_direction') == 'in':
                find_operator(alias, conf.get('operator'))

        if event.get('data', {}).get('service_type') == 'waiting_room' and not event.get('data', {}).get('has_media'):
            db_help.db_add(db_api, event)

    elif event_type == 'participant_disconnected':
        logging.info(f'Event type is {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)
        db_help.db_delete(db_api, event)