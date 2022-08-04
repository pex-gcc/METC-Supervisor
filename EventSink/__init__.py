from ast import operator
import logging

import azure.functions as func

def main(req: func.HttpRequest, QueueAllEvents: func.Out[str]) -> func.HttpResponse:
    request_body = req.get_body()
    
    QueueAllEvents.set(request_body)
    logging.info(f'Incoming event sent to all events queue')
      
    return 'OK'