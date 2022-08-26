import os
import logging
from typing import Container, Iterable

from azure.cosmos import exceptions, CosmosClient, PartitionKey

def get_client() -> CosmosClient:
    # Get Cosmos client from 'DatabaseEndpoint' environment variable, which is Cosmos endpoint
    AccountEndpoint = os.environ.get("DatabaseEndpoint")
    endpoint = AccountEndpoint.split(";")[0].split('=')[1]
    key = AccountEndpoint.split("AccountKey=")[1]
    if endpoint and key:
        return CosmosClient(endpoint, key)
    else:
        logging.info(f'cosmosdb_helpers.get_client: Could not get endpoint and key from environment variable "DatabaseEndpoint"')
        raise exceptions.CosmosResourceNotFoundError(message="Missing endpoint or key in request - verify 'DatabaseEndpoint' environment variable")    

# Get database container
def db_init(database_name: str, container_name: str, partition_key: str) -> Container:
    client = get_client()
    
    # Get the database object, create database if it doesn't exist
    if database_name:
        database = client.create_database_if_not_exists(id=database_name)
    else:
        logging.info(f'cosmosdb_helpers.db_init: Blank database name')
        return None

    if not container_name:
        logging.info(f'cosmosdb_helpers.db_init: Blank container name')
        return None
            
    # Create partition key object with the passed string (which should be in the form of '/<key>')
    pk = PartitionKey(partition_key, kind='Hash')
    
    # Get the container object, create container if it doesn't exist
    container = database.create_container_if_not_exists(id=container_name, partition_key=pk)

    return container

# Add object to specified container, generate an id if it is not defined
def db_add(container: Container, event: dict) -> None:
    try:
        container.create_item(body=event, enable_automatic_id_generation=True)
    except exceptions.CosmosResourceExistsError:
        logging.info(f'cosmosdb_helpers.db_add: Event already in database')
    
    return

# Delete object from specified container
# Get defined partition key from container, walk the data to find value of specified partition key
def db_delete(container: Container, event: dict) -> None:
    pk_path = container.read().get('partitionKey').get('paths')[0]
    pk = event
    for k in [k for k in pk_path.split('/') if k]:
        pk = pk.get(k, {})
    if not pk:
        logging.info(f'cosmosdb_helper.db_delete: Partition key not found.  Nothing to delete')
        return
    if 'id' in event:
        try:
            container.delete_item(item = event.get('id', None), partition_key=pk)
        except exceptions.CosmosResourceNotFoundError:
            logging.info(f'cosmosdb_helpers.db_delete: Item does not exist.  Cannot delete.')
            return
    else:
        logging.info(f'cosmosdb_helpers.db_delete: Item did not have id or partition key field to allow deletion.')
        logging.info(f'cosmosdb_helpers.db_delete: {event}')
        
    return

# Query database to return data from passed SQL query string
def db_query(container: Container, query: str) -> Iterable:
    results = list(container.query_items(query=query, enable_cross_partition_query=True))
    
    return results  

# Delete passed container
def db_clean(container_name: str) -> None:
    client = get_client()
    try:
        database = client.get_database_client(database=os.environ.get('EventsDatabaseName', None))
    except exceptions.ResourceNotFoundError:
        logging.info(f'cosmosdb_helpers.db_clean: Unable to find database')
        return
    container = database.get_container_client(container_name)
    
    database.delete_container(container)
    
    return