# MOBILE-001: Mobile Platform Support Policy

## State

IN_PROGRESS

## Problem Statement

Currently, there is no formal enforcement of mobile OS version support, leading to potential inconsistency in user experience and maintenance burden. Without a clear policy, teams may support too many old versions (increasing testing cost) or drop support too early (harming users).

## User Story

As a Mobile Engineer, I want a clear governance rule for OS version support (Current + 2) so that I know which devices to test against and when to drop support for older versions.

## Acceptance Criteria

- [ ] **Rule File Created**: A new rule file `.agent/rules/mobile-platform-support.mdc` exists.
- [ ] **Policy defined**: The rule specifies support for Current + 2 major versions for iOS and Android.
- [ ] **Technical Enforcement**: The rule mandates that `android/build.gradle` (`minSdkVersion`) and `ios/Podfile` (`platform :ios`) must be updated to match the policy (Advice from @Mobile).
- [ ] **Main Index Updated**: `.agent/rules/main.mdc` references the new rule.
- [ ] **Workflow Impact**: The `/panel`, `/runbook`, and `@[/implement]` workflows indirecty enforce this via the rules directory.
- [ ] **Analytics Verification**: Verify that dropping support does not exclude >5% of active users (Advice from @Product).
- [ ] **User Notice Strategy**: If a version with significant usage is dropped, a plan for user notification is required (Advice from @Compliance).
- [ ] **CI/Test Updates**: CI pipelines and Device Lab configurations are updated to target the supported versions (Advice from @QA).
- [ ] **Deep Link Verification**: Deep link functionality is verified on new OS versions to prevent regressions (Advice from @Security).

## Non-Functional Requirements

- **Compliance**: Adheres to general governance structure.
- **Maintainability**: Centralized rule definition prevents drift.
- **Security**: Reduces attack surface by dropping support for unpatched OS versions.

## Linked ADRs

- ADR-020

## Impact Analysis Summary

- **Components touched**: `.agent/rules/`, `android/build.gradle`, `ios/Podfile`, CI configurations.
- **Workflows affected**: `/panel`, `/runbook`, `@[/implement]` (via rule inheritance)
- **Risks identified**:
    - **User Drop-off**: Potential loss of users on very old devices (mitigated by analytics check).
    - **Deep Links**: Risk of breaking changes in new OS versions (mitigated by verification step).

## Test Strategy

- Manual verification of file creation and content.
- Verify `agent preflight` (if applicable) or manual inspection of rule loading (implied).
- **Sunset Test**: Final test pass on dropped versions to ensure graceful failure/message (Advice from @QA).

## Rollback Plan

- Delete `.agent/rules/mobile-platform-support.mdc`
- Revert changes to `.agent/rules/main.mdc`
- Revert `minSdkVersion` / `Podfile` changes if deployed.
