from ast import operator
import logging

import azure.functions as func
import cosmosdb_helpers as db_help
import json
import re
import os

# This function reads request from Pexip and returns service configuration
def main(req: func.HttpRequest) -> func.HttpResponse:
    policy_response = None

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

    logging.info(f'PolicyServer: /service/configuration http trigger function processed a request.')

    config_db_name = os.environ.get('EventsDatabaseName', None)
    if not config_db_name:
        logging.info(f'PolicyServer: Missing config db name.  Check ''EventsDatabaseName'' environment variable')
        return func.HttpResponse(
           json.dumps(policy_response_continue),
            mimetype='application/json',
            status_code=200
        )
    
    config_container_name = os.environ.get('ConfigContainerName', None)
    if not config_container_name:
        logging.info(f'PolicyServer: Missing config container name.  Check ''ConfigContainerName'' environment variable')
        return func.HttpResponse(
           json.dumps(policy_response_continue),
            mimetype='application/json',
            status_code=200
        )
    
    # Initialize configuration database    
    db_config = db_help.db_init(config_db_name, config_container_name, '/response/result/service_tag')

    config = db_help.db_query(db_config, 'SELECT * FROM ControlConfig')

    # Get local alias from passed-in parameters    
    local_alias = req.params.get('local_alias')

    # If local_alias is missing, reject the call
    if not local_alias:
        policy_response = policy_reponse_reject

    # Check local alias against config database
    else:
        for conf in config:
            match = re.match(conf.get('alias', r'(?!x)x'), local_alias)
            if match:
                policy_response = conf.get('response', None)
                if policy_response and 'basename' in conf and conf.get('basename', None) and len(list(match.groups())) > 0:
                    policy_response['result']['name'] = conf.get('basename') + match.group(1)
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