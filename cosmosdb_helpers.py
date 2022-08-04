import os

from azure.cosmos import exceptions, CosmosClient, PartitionKey

# Get database container
def db_init(database_name, container_name, partition_key):
    
    # Get Cosmos client from 'DatabaseEndpoint' environment variable, which is Cosmos endpoint
    AccountEndpoint = os.environ["DatabaseEndpoint"]
    endpoint = AccountEndpoint.split(";")[0].split('=')[1]
    key = AccountEndpoint.split("AccountKey=")[1]
    client = CosmosClient(endpoint, key)
    
    # Get the database object, create database if it doesn't exist
    database = client.create_database_if_not_exists(id=database_name)
    
    # Create partition key object with the passed string (which should be in the form of '/<key>')
    pk = PartitionKey(partition_key, kind='Hash')
    
    # Get the container object, create container if it doesn't exist
    container = database.create_container_if_not_exists(id=container_name, partition_key=pk)

    return container

# Add object to specified container, generate an id if it is not defined
def db_add(container, event):
    container.create_item(body=event, enable_automatic_id_generation=True)

# Delete object from specified container
# Get defined partition key from container, walk the data to find value of specified partition key
def db_delete(container, event):
    pk_path = container._properties['partitionKey']['paths'][0]
    pk = event
    for k in pk_path.split('/'):
        if k:
            pk = pk[k]
    container.delete_item(item = event['id'], partition_key=pk)

# Query database to return data from passed SQL query string
def db_query(container, query):
    results = list(container.query_items(query=query, enable_cross_partition_query=True))
    return results  

#Delete passed container
def db_clean(database_name, container_name):
    AccountEndpoint = os.environ["DatabaseEndpoint"]
    endpoint = AccountEndpoint.split(";")[0].split('=')[1]
    key = AccountEndpoint.split("AccountKey=")[1]
    client = CosmosClient(endpoint, key)
    database = client.get_database_client(database=database_name)
    database.delete_container(container_name)    