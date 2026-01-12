# SOC2 Compliance Checklist

## Access Control
- [ ] Production access is restricted.
- [ ] Changes are reviewed (PRs).
- [ ] MFA is enabled for all system access.

## Audit Logs
- [ ] Critical actions (login, data modification) are logged.
- [ ] Logs are immutable and stored centrally.

## Change Management
- [ ] All code changes are linked to a Story/Ticket.
- [ ] CI/CD pipelines run automated tests.
- [ ] No direct commits to `main` (branch protection).

## Risk Management
- [ ] Vulnerability scanning is enabled.
- [ ] Dependencies are patched.
