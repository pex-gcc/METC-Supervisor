from ast import operator
import logging

import azure.functions as func

# To provoke Github workflow
def main(req: func.HttpRequest, QueueAllEvents: func.Out[str]) -> func.HttpResponse:
    request_body = req.get_body()
    
    # Send incoming event to message queue for further processing and log it
    QueueAllEvents.set(request_body)
    logging.info(f'Incoming event sent to all events queue')
      
    return 'OK'