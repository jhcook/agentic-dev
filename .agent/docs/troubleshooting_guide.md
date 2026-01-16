# Troubleshooting Guide

## Sync Operations

### Handling Sync Interruptions
If a sync operation is interrupted, the process can be safely resumed by re-invoking the sync command. The system will continue from the last successfully processed page of records, ensuring data consistency and integrity.

### Common Error Codes
- `ErrorCode 502`: Network issues during sync. Ensure your connection is stable.
- `ErrorCode 404`: Data requested not found, verify the dataset availability.

[...]