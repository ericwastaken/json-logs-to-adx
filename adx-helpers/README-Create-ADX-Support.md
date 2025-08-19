# README - How to create ADX support for ingesting logs

## How to get a FREE AZURE CLUSTER

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

## KQL Commands

- Create a table to ingest Docker Logs.
- Setup streaming ingestion
- Setup ingestion mapping (two properties: timestamp, event)
- Verify ingestion mapping

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