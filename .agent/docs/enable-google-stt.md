<!--
Copyright 2026 Justin Cook

-->

# Enable Google STT

## Instructions

Use `gcloud` to create the service account, credentials, and bindings. Note identifying information has been scrubbed from the example below:

```shell
$ gcloud iam service-accounts create \
    speech-to-text-agent-dev \
    --project <project name>
Created service account [speech-to-text-agent-dev].

$ gcloud projects \
    add-iam-policy-binding \
    <project name> --member \
    serviceAccount:speech-to-text-agent-dev@<project-id>.iam.gserviceaccount.com \
    --role roles/speech.editor
Updated IAM policy for project
...

$ gcloud iam service-accounts keys \
    create speech-to-text-key.json \
    --iam-account \
    speech-to-text-agent-dev@<project name>.iam.gserviceaccount.com
created key [<the keys id>] of type [json] as [speech-to-text-key.json] for [speech-to-text-agent-dev@<project name>.iam.gserviceaccount.com]

$ gcloud beta services identity \
    create \
    --service=speech.googleapis.com \
    --project=<project name>
Service identity created: service-<service account id>@gcp-sa-speech.iam.gserviceaccount.com

$ project_number=$(gcloud projects \
    list \
    --filter=<project name> \
    --format="value(PROJECT_NUMBER)")

$ gcloud projects \
    add-iam-policy-binding \
    <project name> --member \
    serviceAccount:service-${project_number?}@gcp-sa-speech.iam.gserviceaccount.com \
    --role roles/speech.serviceAgent
Updated IAM policy for project
...

```

Then apply the secret to the secrets manager:

```shell
$ agent secret set google application_credentials_json --value "$(cat ~/speech-to-text-key.json)"
✅ Secret 'google.application_credentials_json' saved successfully.
```
