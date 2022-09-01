# This function is the orchestrator for the APIClientRefresh activity
# It will wait for 40 seconds and then call APIClient, which will refresh the token

from datetime import datetime, timedelta
import logging
import json

import azure.functions as func
import azure.durable_functions as df

def orchestrator_function(context: df.DurableOrchestrationContext):
    call_info = context.get_input()
    if call_info and call_info.get('id', False):
        logging.info(f'Orchestration started - {call_info.get("id", "")}')
        # deadline = context.current_utc_datetime + timedelta(seconds=delay)
        next_time = datetime.strptime(call_info.get('next_update'), '%Y-%m-%d %H:%M:%S.%f')
        yield context.create_timer(next_time)
        call_info['next_update'] = datetime.strftime(context.current_utc_datetime + timedelta(seconds=40), '%Y-%m-%d %H:%M:%S.%f')
        call_info = yield context.call_activity('APIClientRefresh', call_info)
        
        context.continue_as_new(call_info)

main = df.Orchestrator.create(orchestrator_function)