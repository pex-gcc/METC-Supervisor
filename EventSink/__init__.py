from ast import operator
import logging
import json

import azure.functions as func

def main(req: func.HttpRequest, QueueAllEvents: func.Out[str], QueueParticipantEvents: func.Out[str]) -> func.HttpResponse:
    request_body = req.get_body()
    event = json.loads(request_body)
    
    QueueAllEvents.set(request_body)
    logging.info(f'Incoming event sent to all events queue')

    # Check event type and add or remove to active calls db
    if 'event' in event:    
        event_type = event['event']
        logging.info(f'Event type is: {event_type}')
        
        if event_type == 'participant_connected' or event_type == 'participant_disconnected':
            QueueParticipantEvents.set(request_body)
            logging.info(f'Incoming event sent to participants queue')
       
    return 'OK'