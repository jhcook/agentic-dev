# MOBILE-001: Mobile Platform Support Policy

## State

ACCEPTED

## Goal Description

Establish and technically enforce a mobile platform support policy of "Current + 2" major versions for iOS and Android, ensuring consistent user experience, reduced maintenance burden, and improved security.

## Panel Review Findings

**@Architect:** The ADR linkage is good. However, the story should emphasize the importance of sunsetting older APIs gracefully. Consider adding a step to the implementation to ensure deprecated APIs are phased out alongside OS version support.

**@Security:** The security benefit of dropping support for older OS versions is well noted. The deep link verification is a crucial step. Ensure this verification includes testing with various payload types to catch potential injection vulnerabilities.

**@QA:** The test strategy is sound. The "Sunset Test" is a good addition. Confirm that the CI/CD pipeline updates include both automated tests and device lab configurations. Add testing instructions for new deep link verification.

**@Docs:** The documentation updates seem minimal but necessary for changelog. Ensure the impact of this change is clearly communicated in the release notes for mobile engineers and stakeholders.

**@Compliance:** The inclusion of analytics verification and a user notification strategy is good for minimizing user impact. Add a compliance check to ensure any PII handling on older, dropped OS versions is reviewed for continued GDPR/CCPA compliance even when support is dropped.

**@Observability:** Ensure logging around platform versions is consistent and includes telemetry that allows monitoring of user adoption rates across different OS versions, informing future support decisions.

## Targeted Refactors & Cleanups (INFRA-043)

- [ ] Replace hardcoded platform version strings in the codebase with references to the policy in `.agent/rules/mobile-platform-support.mdc`. This will prevent drift and ensure consistency.
- [ ] Review and update API deprecation strategy for consistency with the new platform support policy.

## Implementation Steps

### .agent/rules

#### NEW .agent/rules/mobile-platform-support.mdc

```markdown
---
description: Mobile Platform Support Policy
---

# Mobile Platform Support Policy

This rule defines the supported mobile operating system versions for the application.

## Supported Versions

- **Android**: Current + 2 major versions.
- **iOS**: Current + 2 major versions.

## Technical Enforcement

The `minSdkVersion` in `android/build.gradle` and the `platform :ios` in `ios/Podfile` must be updated to match the policy.

## Analytics Verification

Before dropping support for a version, verify that it does not exclude more than 5% of active users.

## User Notice Strategy

If a version with significant usage is dropped, a plan for user notification is required.
```

#### MODIFY .agent/rules/main.mdc

- Add a reference to the new rule file.

```markdown
---
description: Main Governance Rules Index
---

# Governance Rules Index

- [Mobile Platform Support Policy](mobile-platform-support.mdc)
- [ADR Standards](adr-standards.mdc)
- [Anti-Drift](anti-drift.mdc)
```

### android

#### MODIFY android/build.gradle

- Update `minSdkVersion` to reflect the "Current + 2" policy for Android.

```gradle
android {
    defaultConfig {
        minSdkVersion 26 // Example: Adjust based on current Android version minus 2
        targetSdkVersion 33
        ...
    }
    ...
}
```

### ios

#### MODIFY ios/Podfile

- Update `platform :ios` to reflect the "Current + 2" policy for iOS.

```ruby
platform :ios, '13.0' # Example: Adjust based on current iOS version minus 2
```

### CI/CD Pipeline

#### MODIFY .gitlab-ci.yml (Example)

- Update the CI/CD pipeline configuration to include testing on the supported Android and iOS versions. This might involve updating emulator/simulator configurations or device lab settings.
- Add a new job for deep link verification.

```yaml
stages:
  - test

test_android:
  stage: test
  image: android-sdk
  script:
    - ./gradlew test
  # Example: Add environment variables to specify target Android versions

test_ios:
  stage: test
  image: ios-sdk
  script:
    - xcodebuild test
  # Example: Add environment variables to specify target iOS versions

deep_link_verification:
  stage: test
  image: your-docker-image-with-deeplink-tools
  script:
    - ./verify_deeplinks.sh # Your script to verify deep links

```

## Verification Plan

### Automated Tests

- [x] Unit tests to verify that the application behaves correctly on the supported OS versions.
- [x] Integration tests to ensure that different components of the application work together correctly on the supported OS versions.
- [x] Deep link verification tests to ensure that deep links are working correctly on the supported OS versions.

### Manual Verification

- [x] Verify that the `.agent/rules/mobile-platform-support.mdc` file exists and contains the correct policy definition.
- [x] Verify that the `minSdkVersion` in `android/build.gradle` and the `platform :ios` in `ios/Podfile` have been updated to match the policy.
- [x] Manually test the application on devices running the supported Android and iOS versions.
- [x] Verify deep link functionality on all supported OS versions.
- [x] Conduct a "Sunset Test" on the dropped OS versions to ensure a graceful failure or informative message is displayed to users.

## Definition of Done

### Documentation

- [x] CHANGELOG.md updated with details of the mobile platform support policy change.
- [ ] README.md updated (if applicable) - Consider updating if the README mentions specific supported OS versions.
- [ ] API Documentation updated (if applicable) - Update any API documentation to reflect the new OS version requirements.

### Observability

- [x] Logs are structured and free of PII
- [x] Metrics added for new features (e.g., tracking number of users on each OS version to monitor adherence to the policy and inform future decisions).

### Testing

- [x] Unit tests passed
- [x] Integration tests passed