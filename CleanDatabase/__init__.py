import logging

import azure.functions as func
import os
import cosmosdb_helpers as db_help

def main(req: func.HttpRequest) -> func.HttpResponse:
    container_name = req.params.get('container')
    
    if container_name:
        db_help.db_clean(container_name)
    
    return 'OK'