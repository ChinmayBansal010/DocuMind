# Privacy Policy

_Last updated: 14 November 2026_

## Scope
This release is a self-hosted, single-user application intended to run on a device you control. It is not a hosted account service.

## Data stored
Uploaded documents, extracted text, filenames, file hashes and basic activity records are stored in the application data directory and SQLite database on the machine running DocuMind.

## Processing and third-party services
Local parsing, search and storage run on your device. If configured, Azure AI Search receives extracted text chunks for indexing; Azure Document Intelligence receives the selected original file when layout extraction is requested. Azure AI Content Safety receives user questions, generated answers and generated contract reports for moderation. Prompt Shields receives user prompts and retrieved passages, and the first 10,000 characters of a contract during contract analysis. Azure AI Language receives up to 5,000 characters from a selected document when insights are explicitly requested and may return detected PII entities. Azure AI Translator receives only text submitted for translation. Ollama receives the full extracted contract text (up to 40,000 characters) during contract analysis, and questions plus retrieved passages during Q&A. Review each provider's own privacy terms and retention rules.

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
