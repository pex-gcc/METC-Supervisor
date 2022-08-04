from ast import operator
import logging

import azure.functions as func
import json

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('/service/configuration http trigger function processed a request.')

    # default responses
    policy_reponse_reject = {
        "status" : "success",
        "action" : "reject"
        }

    policy_response_continue = {
        "status" : "success",
        "action" : "continue"
        }

    # test response
    policy_response_test = {
            "status" : "success",
            "action" : "continue",
            "result" : {
                "service_type" : "conference",
                "name" : "External Policy",
                "service_tag" : "policy"
                }
            }

    local_alias = req.params.get('local_alias')

    if not local_alias:
        policy_response = policy_reponse_reject

    elif local_alias == 'external':
        policy_response = policy_response_test
        
    elif local_alias == 'external_reject':
        policy_response = policy_reponse_reject

    else:
        policy_response = policy_response_continue

    return func.HttpResponse(
        json.dumps(policy_response),
        mimetype='application/json',
        status_code=200
    )