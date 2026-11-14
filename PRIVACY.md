# Privacy Policy

_Last updated: 14 November 2026_

## Data handled

Neon Managed Auth handles registration credentials and browser sessions. DocuMind stores the verified Auth subject, profile, projects, contracts, versions, extracted text, search chunks, analysis results, conversations, obligations, deadlines, and audit records in the configured Neon PostgreSQL branch. Original uploads are stored in the configured local data directory (or persistent container volume).

## Processing

PDF and DOCX content is sent to the configured Azure AI Document Intelligence resource; DOCX files are first converted locally to PDF. TXT is decoded locally. Extracted text is processed by Azure AI Language for language detection, named entities, and key phrases, and by Azure AI Content Safety for moderation and prompt-injection screening. When a user requests translation, the chosen contract text or saved summary is sent to Azure AI Translator's text API. Original-format document translation is not used.

Contract chunks, page numbers, document labels, opaque owner/project/contract/version identifiers, and locally generated Ollama vectors are sent to the configured Azure AI Search index for hybrid text/vector retrieval. Search queries are restricted by verified owner and project IDs and only the latest contract versions. If enabled, Ollama receives contract text for local reasoning and retrieved passages plus the user's question for assistant answers. Configure Azure and Ollama with appropriate access controls, retention settings, and regional availability; review their data-processing terms before uploading contracts.

Only Azure AI F0/Free service capabilities are used. F0 quotas and Search Free storage limits can cause processing failures; those failures are reported rather than silently bypassed. Application-side monthly counters track Doc Intelligence pages, Language and Content Safety text records, and Translator characters, but other Azure subscription workloads may independently consume the same service quotas.

## Security and retention

Database and local file retention follow the operator's Neon, host, backup, and deletion policies. Deleting a project removes its application records and locally stored source files. Optional AES-GCM file encryption protects source files only; extracted text and related records remain in PostgreSQL without application-level encryption. Keep encryption keys and backups secure.

## AI-generated content

AI findings can be incomplete or wrong. Source excerpts and available page references are included to support review; they do not establish legal conclusions. Verify results against the complete original document.

## Publisher information

The publisher's legal identity, contact, jurisdiction, retention periods, and privacy-request process have not been supplied. Complete these items before offering a hosted commercial service.

> This document is a project template, not legal advice or a compliance certification.
