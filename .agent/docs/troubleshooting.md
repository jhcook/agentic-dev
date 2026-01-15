# Troubleshooting

## Common Issues

### Sync Failed: "Cannot push without SUPABASE_ACCESS_TOKEN"
**Solution**:
You need to set your Supabase Access Token.
1.  Get a token from Supabase Dashboard.
2.  Add `SUPABASE_ACCESS_TOKEN=your_token` to `.env`.
3.  Or verify `.agent/secrets/supabase_access_token` exists.

### Preflight Failed: "Governance violation"
**Solution**:
Read the failure message carefully. It usually points to a specific rule violation (e.g., missing tests, architecture violation). Fix the code to comply with the rule.

### "Validation Error" in Story
**Solution**:
Ensure your story markdown follows the template schema. Use `agent new-story` to get the correct format.
