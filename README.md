# Project Synopsis

[...]

## Sync Features
Our synchronization command now supports handling large datasets more efficiently. If you work with large datasets, you can now customize the pagination size using the environment variable `AGENT_SYNC_PAGE_SIZE`. This setting allows the sync operation to fetch and process the data in manageable chunks, preventing memory overloads and ensuring smoother operations.

[...]

## Environment Variables
- `AGENT_SYNC_PAGE_SIZE`: Sets the number of records to sync per page request. Useful for large dataset operations. Default is `500`.

[...]

## Troubleshooting Guide
Refer to the troubleshooting section below for common issues and solutions during sync operations.

[...]