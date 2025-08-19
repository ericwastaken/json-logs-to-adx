# README - ADX Preparation

## How to get a FREE ADX CLUSTER

1. Sign up for an Azure Free Account at https://azure.microsoft.com/free/
    - You'll need a credit card for verification (won't be charged)
    - Get $200 credit for 30 days
    - Access to free services for 12 months

2. Create a free Azure Data Explorer Cluster:
    - Go to Azure ADX Portal (https://dataexplorer.azure.com/)
    - Follow the steps to create your free cluster.

3. Configure the new cluster:
    - Wait for deployment to complete
    - Go to your new cluster
    - Create a new database
    - Use the cluster URI shown in "Overview"

## How to create an ADX structure for ingesting logs

At a high lebel, this is what you need to do:
- Create a table to ingest Docker Logs.
- Setup streaming ingestion
- Setup ingestion mapping (two properties: timestamp, event)
- Verify ingestion mapping

### KQL Commands

Replace:
- `docker-logs` with the name of the table you want to create.
- `TestDB` with the name of the database you want to create.

Whe creating the ingestion mapping, we are creating a structure of two properties:
- timestamp: datetime - this is the timestamp of the log.
- event: dynamic (json) - this is where the actual log will be stored.

```text
// Create the table (safe if run repeatedly)
.create table ['docker-logs'] (timestamp:datetime, event:dynamic)

// Turn on streaming at DB and table level
.alter database ['TestDB'] policy streamingingestion enable

// Table-level
.alter table ['docker-logs'] policy streamingingestion enable

// Add Ingestion Meta
.alter table ['docker-logs'] policy ingestiontime true

// Create the ingestion mapping
.create-or-alter table ['docker-logs'] ingestion json mapping "docker_logs_json_mapping" '[{ "column": "event", "datatype": "dynamic",  "Properties": { "Path": "$" } },{ "column": "timestamp", "datatype": "datetime", "Properties": { "Path": "$.timestamp" } }]'

// verify
.show table ['docker-logs'] ingestion json mappings
```