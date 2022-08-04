import logging
import json
import os

import azure.functions as func
import cosmosdb_helpers as db_help

db_events = None

# This function is triggered when an event is passed into the queue
def main(msg: func.QueueMessage) -> None:
    global db_events

    # Get event json data from queue
    logging.info(f'All event queue trigger processed new item: {msg.id}, inserted: {str(msg.insertion_time)}')
    event = json.loads(msg.get_body())

    # Initialize "all events" database when function is first loaded, object stored globally in `db_events` after this
    if db_events is None:
        db_events = db_help.db_init(os.environ["EventsDatabaseName"], os.environ["EventsContainerName"], '/event')

    # Send all event to events container to store for reporting
    db_help.db_add(db_events, event)
