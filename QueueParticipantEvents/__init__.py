import logging
import json
import re

import azure.functions as func
import cosmosdb_helpers as db_help
from client import call_operators, get_env

def main(msg: func.QueueMessage) -> None:
    events_db_name = get_env('EventsDatabaseName')
    activecalls_container_name = get_env('ActiveCallsContainerName')
    config_container_name = get_env('ConfigContainerName')

    # Initialize databases
    db_events = db_help.db_init(events_db_name, activecalls_container_name, '/data/service_tag')
    db_config = db_help.db_init(events_db_name, config_container_name, '/response/result/service_tag')

    # Get configuration info
    config = db_help.db_query(db_config, f'SELECT * FROM {config_container_name}')
    
    # Get event json data from queue
    logging.info(f'QueueParticipantEvents.main: Participant queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event_data =  msg.get_body()
    event = json.loads(event_data)
    event_type = event.get('event')
    event['id'] = event.get('data', {}).get('call_id')
    id = event.get('id', '')
    
    if not id:
        return
   
    if event_type == 'participant_connected':
        logging.info(f'QueueParticipantEvents.main: Event {id} is type {event_type}, sending to active calls db')
        db_help.db_add(db_events, event)
        
        call_info = {}
        call_info['destination_alias'] = event.get('data', {}).get('destination_alias')
        call_info['conference'] = event.get('data', {}).get('conference')

        if call_info.get('destination_alias', None):
            conf = None
            for c in config:
                match = re.match(c.get('alias'), call_info.get('destination_alias'))
                if match:
                    conf = c
                    break
            
            call_info['dialout'] = conf.get('dialout', None)
            if conf and conf.get('dialout') and event.get('data', {}).get('call_direction') == 'in':
                logging.info(f'QueueParticipantEvents.main: Dialing from {call_info.get("destination_alias", "")} to {call_info.get("conference", "")}')
                call_operators(call_info)

    elif event_type == 'participant_disconnected':
        logging.info(f'QueueParticipantEvents.main: Event {id} is type {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)