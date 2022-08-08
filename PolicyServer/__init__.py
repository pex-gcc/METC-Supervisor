from ast import operator
import logging

import azure.functions as func
import cosmosdb_helpers as db_help
import json
import re
import os

db_config = None

# This function reads request from Pexip and returns service configuration
def main(req: func.HttpRequest) -> func.HttpResponse:
    global db_config
    policy_response = None
    
    logging.info('/service/configuration http trigger function processed a request.')

    # Initialize configuration database    
    if db_config is None:
        db_config = db_help.db_init(os.environ['EventsDatabaseName'], os.environ['ConfigContainerName'], '/response/result/service_tag')

    config = db_help.db_query(db_config, 'SELECT * FROM ControlConfig')

    # response to reject call
    policy_reponse_reject = {
        "status" : "success",
        "action" : "reject"
        }

    # response to pass back to Pexip to check internally
    policy_response_continue = {
        "status" : "success",
        "action" : "continue"
        }

    # Get local alias from passed-in parameters    
    local_alias = req.params.get('local_alias')

    # If local_alias is missing, reject the call
    if not local_alias:
        policy_response = policy_reponse_reject

    # Check local alias against config database
    else:
        for conf in config:
            match = re.match(conf['regex'], local_alias)
            if match:
                policy_response = conf['response']
                policy_response['name'] = conf['basename'] + match.group(1)
                break
            
    # For anything else pass back to Pexip
    if not policy_response:        
        policy_response = policy_response_continue

    # Return the response as type 'application/json'
    return func.HttpResponse(
        json.dumps(policy_response),
        mimetype='application/json',
        status_code=200
    )