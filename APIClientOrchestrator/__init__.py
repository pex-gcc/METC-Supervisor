# This function is not intended to be invoked directly. Instead it will be
# triggered by an HTTP starter function.
# Before running this sample, please:
# - create a Durable activity function (default name is "Hello")
# - create a Durable HTTP starter function
# - add azure-functions-durable to requirements.txt
# - run pip install -r requirements.txt

from datetime import timedelta
import logging
import json

import azure.functions as func
import azure.durable_functions as df


def orchestrator_function(context: df.DurableOrchestrationContext):
    base = context.get_input()
    logging.info(f'Orchestration started - {base}')
    result1 = yield context.call_activity('APIClientRefresh', f"{base}0")
    for i in range(1, 5):
        deadline = context.current_utc_datetime + timedelta(seconds=10)
        yield context.create_timer(deadline)
        yield context.call_activity('APIClientRefresh', f"{base}{i}")
    return result1

main = df.Orchestrator.create(orchestrator_function)