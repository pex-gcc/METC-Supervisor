import logging
import json
import re

import azure.functions as func
import azure.durable_functions as df
import cosmosdb_helpers as db_help
from client import call_operators, end_api, get_env

async def main(msg: func.QueueMessage, APIOrchestrationClient: str) -> None:
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
    
    client = df.DurableOrchestrationClient(APIOrchestrationClient)
    
    if event_type == 'participant_connected':
        logging.info(f'QueueParticipantEvents.main: Event {id} is type {event_type}, sending to active calls db')
        db_help.db_add(db_events, event)
        
        # alias = event.get('data', {}).get('destination_alias')
        alias = event.get('data', {}).get('alias')
        conference = event.get('data', {}).get('conference')
        if alias:
            conf = None
            for c in config:
                match = re.match(c.get('alias'), alias)
                if match:
                    conf = c
                    break

            if conf and conf.get('operator') and event.get('data', {}).get('call_direction') == 'in':
                await call_operators(alias, conference, conf.get('operator'), client)

    elif event_type == 'participant_disconnected':
        logging.info(f'QueueParticipantEvents.main: Event {id} is type {event_type}, deleting from active calls db ')
        db_help.db_delete(db_events, event)
        
    elif event_type == 'participant_updated':
        if event.get('data', {}).get('has_media') or event.get('data', {}).get('service_type') != 'conference':
            return
        call_id = event.get('data', {}).get('call_id')
        logging.info(f'QueueParticipantEvents.main: Participant update event received for : {event.get("data", {}).get("display_name")} calling {event.get("data", {}).get("conference")}')

        if call_id:
            apitokens_container_name = get_env('APITokenContainerName')
            db_api = db_help.db_init(events_db_name, apitokens_container_name, '/operator')
            
            query = f'SELECT * FROM {apitokens_container_name} c WHERE c.id = "{call_id}"'
            api_call = db_help.db_query(db_api, query)
            if api_call:
                logging.info(f'QueueParticipantEvents.main: End API event called for : {event.get("data", {}).get("display_name")} calling {event.get("data", {}).get("conference")}')
                end_api(call_id, client)