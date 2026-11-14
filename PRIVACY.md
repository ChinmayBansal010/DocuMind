# Privacy Policy

_Last updated: 14 November 2026_

## Scope
This release is a self-hosted, single-user application intended to run on a device you control. It is not a hosted account service.

## Data stored
Uploaded documents, extracted text, filenames, file hashes and basic activity records are stored in the application data directory and SQLite database on the machine running DocuMind.

## Processing and third-party services
Local parsing, search and storage run on your device. If configured, Azure AI Search receives extracted text chunks for indexing; Azure Document Intelligence receives the selected original file when cloud extraction is requested; Azure AI Content Safety may receive questions or submitted text for moderation. Ollama receives the question and retrieved document passages when local AI generation is enabled. Review each provider's own privacy terms and retention rules.

## AI-generated content
AI answers may be incomplete or incorrect. Review cited passages and original files before relying on an answer.

## Retention and deletion
Local documents remain until you delete them or remove the application data directory. Deleting local copies does not automatically delete copies already sent to third-party providers; their retention policies apply.

## Security
DocuMind does not encrypt local files or its database. Protect your device account, use full-disk encryption and secure backups. Do not expose this release to the public internet.

## Sensitive information
Do not upload highly sensitive personal, financial, health, legal or children's information unless you have assessed the risks and any enabled third-party service is suitable.

## Publisher and privacy contact
The publisher's verified legal name, privacy contact, jurisdiction and privacy-request process have not been supplied. These must be completed before commercial distribution.

> This is a starter template, not legal advice or a compliance certification.
