import logging
import json

import azure.functions as func
import cosmosdb_helpers as db_help

db_events = None

def main(msg: func.QueueMessage) -> None:
    global db_events

    # Get event json data from queue
    logging.info(f'All event queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event = json.loads(msg.get_body())

    # outEvents.set(func.Document.from_json(msg.get_body()))
    # Initialize "all events" database    
    if db_events is None:
        db_events = db_help.db_init('eventDatabase', 'events', '/event')

    # Send all event to events container to store for reporting
    db_help.db_add(db_events, event)
