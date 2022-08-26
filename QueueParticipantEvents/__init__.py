import logging
import json
import os
import re

import azure.functions as func
import cosmosdb_helpers as db_help
from client import find_operator, end_api

api_clients = {}

def main(msg: func.QueueMessage) -> None:
    global api_clients

    events_db_name = os.environ.get('EventsDatabaseName', None)
    if not events_db_name:
        logging.info(f'QueueParticipantEvents: Missing config db name.  Check ''EventsDatabaseName'' environment variable')
        return

    activecalls_container_name = os.environ.get('ActiveCallsContainerName', None)
    if not activecalls_container_name:
        logging.info(f'QueueParticipantEvents: Missing active calls container name.  Check ''ActiveCallsContainerName'' environment variable')
        return
    
    config_container_name = os.environ.get('ConfigContainerName', None)
    if not config_container_name:
        logging.info(f'QueueParticipantEvents: Missing config container name.  Check ''ConfigContainerName'' environment variable')
        return

    apicalls_container_name = os.environ.get('APICallsContainerName', None)
    if not apicalls_container_name:
        logging.info(f'QueueParticipantEvents: Missing API calls container name.  Check ''APICallsContainerName'' environment variable')
        return

    # Initialize "active calls" database    
    db_events = db_help.db_init(events_db_name, activecalls_container_name, '/data/service_tag')

    # Get call configuration
    db_config = db_help.db_initevents_db_name, config_container_name, '/response/result/service_tag')
    config = db_help.db_query(db_config, f'SELECT * FROM {config_container_name}')

    # Initialize "API calls" database
    db_api = db_help.db_init(events_db_name, apicalls_container_name, '/data/display_name')

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
        
        alias = event.get('data', {}).get('destination_alias')
        conference = event.get('data', {}).get('conference')
        if alias:
            conf = None
            for c in config:
                match = re.match(c.get('alias'), alias)
                if match:
                    conf = c
                    break

            if conf and conf.get('operator') and event.get('data', {}).get('call_direction') == 'in':
                api_clients = find_operator(alias, conference, conf.get('operator'), api_clients)
                logging.info(f'QueueParticipantEvents.main: Number of existing API calls found after find_operator call: {len(api_clients.keys())}')

        if event.get('data', {}).get('service_type') == 'waiting_room' and not event.get('data', {}).get('has_media'):
            db_help.db_add(db_api, event)

    elif event_type == 'participant_disconnected':
        logging.info(f'QueueParticipantEvents.main: Event {id} is type {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)
        db_help.db_delete(db_api, event)
        
    elif event_type == 'participant_updated':
        if event.get('data', {}).get('has_media') or event.get('data', {}).get('service_type') != 'conference':
            return
        call_id = event.get('data', {}).get('call_id')
        logging.info(f'QueueParticipantEvents.main: Participant update event received for : {event.get("data", {}).get("display_name")} calling {event.get("data", {}).get("conference")}')

        query = f'SELECT * FROM {os.environ.get("APICallsContainerName")} c WHERE c.id = "{call_id}"'
        api_call = db_help.db_query(db_api, query)
        if api_call:
            logging.info(f'QueueParticipantEvents.main: End API event called for : {event.get("data", {}).get("display_name")} calling {event.get("data", {}).get("conference")}')
            api_clients = end_api(call_id, api_clients)