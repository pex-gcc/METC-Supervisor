from ast import operator
import logging

import azure.functions as func
import json

# This function reads request from Pexip and returns service configuration
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('/service/configuration http trigger function processed a request.')

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

    # test response to enter a conference
    policy_response_test = {
            "status" : "success",
            "action" : "continue",
            "result" : {
                "service_type" : "conference",
                "name" : "External Policy",
                "service_tag" : "policy"
                }
            }

    # Get local alias from passed-in parameters    
    local_alias = req.params.get('local_alias')

    # If local_alias is missing, reject the call
    if not local_alias:
        policy_response = policy_reponse_reject

    # If 'external' is dialed, pass in the test conference response
    elif local_alias == 'external':
        policy_response = policy_response_test
        
    # If 'external_reject' is dialed, reject the call
    elif local_alias == 'external_reject':
        policy_response = policy_reponse_reject

    # For anything else pass back to Pexip
    else:
        policy_response = policy_response_continue

    # Return the response as type 'application/json'
    return func.HttpResponse(
        json.dumps(policy_response),
        mimetype='application/json',
        status_code=200
    )