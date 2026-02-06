# ADR-020: Mobile Platform Support Policy

## Status

Proposed

## Context

Currently, the project lacks a formal policy for mobile OS version support. This ambiguity leads to several issues:
1.  **Testing Fragmentation**: QA and developers may test on arbitrary versions, missing critical bugs on older OSes or wasting time on obsolete ones.
2.  **Security Risk**: Supporting very old OS versions often means supporting devices that no longer receive security patches, increasing the attack surface.
3.  **Development Velocity**: Trying to support ancient APIs prevents the use of modern platform features (e.g., latest Swift UI, Jetpack Compose features).

## Decision

We will adopt a **Current + 2 Major Versions** support policy for both iOS and Android.

- **iOS**: Support the current major version and the two previous major versions (e.g., if iOS 18 is current, support 18, 17, 16).
- **Android**: Support the current major version and the two previous major versions as the *primary* test targets. `minSdkVersion` will be set to ensure compatibility with these versions.

**Governance Enforcement**:
- The policy will be codified in `.agent/rules/mobile-platform-support.mdc`.
- `android/build.gradle` (`minSdkVersion`) and `ios/Podfile` (`platform :ios`) must be updated to reflect this policy.
- CI/CD pipelines will be updated to test against these specific versions.

## Consequences

- **Positive**:
    - **Focused Testing**: QA and Device Labs can focus resources on a specific, relevant set of devices.
    - **Security**: Reduces risk by dropping support for unpatched, end-of-life OS versions.
    - **Modern Codebase**: Allows developers to use newer APIs and libraries (e.g., adopting new Swift concurrency features that require newer iOS versions).
    - **Predictability**: Users and stakeholders have clear expectations about device support.

- **Negative**:
    - **User Drop-off**: Users on devices older than ~3 years may lose support. This is mitigated by the "Analytics Check" governance rule (<5% impact).
    - **Device Procurement**: The team may need to regularly update test devices to match the "Current" window.
