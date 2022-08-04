import os

from azure.cosmos import exceptions, CosmosClient, PartitionKey

def db_init(database_name, container_name, partition_key):
    AccountEndpoint = os.environ["DatabaseEndpoint"]
    endpoint = AccountEndpoint.split(";")[0].split('=')[1]
    key = AccountEndpoint.split("AccountKey=")[1]
    client = CosmosClient(endpoint, key)
    database = client.create_database_if_not_exists(id=database_name)
    pk = PartitionKey(partition_key, kind='Hash')
    container = database.create_container_if_not_exists(id=container_name, partition_key=pk)

    return container

def db_add(container, event):
    container.create_item(body=event, enable_automatic_id_generation=True)

def db_delete(container, event):
    pk_path = container._properties['partitionKey']['paths'][0]
    pk = event
    for k in pk_path.split('/'):
        if k:
            pk = pk[k]
    container.delete_item(item = event['id'], partition_key=pk)

def db_query(container, query):
    results = list(container.query_items(query=query, enable_cross_partition_query=True))
    return results  

def db_clean(database_name, container):
    AccountEndpoint = os.environ["DatabaseEndpoint"]
    endpoint = AccountEndpoint.split(";")[0].split('=')[1]
    key = AccountEndpoint.split("AccountKey=")[1]
    client = CosmosClient(endpoint, key)
    database = client.get_database_client(database=database_name)
    database.delete_container(container)    