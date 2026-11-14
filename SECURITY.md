# Security & Data Handling

_Last updated: 14 November 2026_

## Authentication and authorization

Email/password authentication is provided by the existing Neon Managed Auth branch using `@neon/auth`. FastAPI verifies EdDSA tokens through the configured JWKS URL, checks the Auth origin as issuer and audience plus expiry, and uses the verified subject as the application user ID. Project, contract, version, conversation, report, and assistant operations are scoped to that user. The API does not accept a caller-supplied owner ID.

Configure the correct branch's `NEON_AUTH_BASE_URL` and `NEON_AUTH_JWKS_URL`, and add every browser origin to Neon Auth's trusted domains. Do not use wildcard CORS origins.

## Stored data

Application records are stored in Neon PostgreSQL. Uploaded source files are stored under generated user/project-scoped paths in `DOCUMIND_DATA_DIR`. File bytes are protected with AES-GCM only when a valid `DOCUMENT_ENCRYPTION_KEY` is configured. Extracted text, chunks, profile data, messages, and analyses are not application-encrypted; use database/provider controls and restrict access accordingly.

Keep encryption keys in a secret manager, not source control. Back up the key separately from encrypted files. Losing the key prevents decryption. Protect backups and restrict filesystem permissions.

## Network and integrations

The supplied Compose file binds to loopback by default. Production deployments should use HTTPS, private database networking where supported, a trusted reverse proxy, restrictive firewall rules, backups, and monitoring. Ollama must not be exposed to untrusted networks.

All five configured Azure AI services are required at application startup. Azure credentials are read from environment variables, are never returned by settings or health endpoints, and are not written to application logs. Azure responses are validated and surfaced as service-specific errors; there are no local-success fallbacks for Azure extraction, moderation, translation, or retrieval failures.

Contract PDFs and locally converted DOCX PDFs are sent to Azure AI Document Intelligence in requests of at most 2 pages and 4 MB. Extracted contract text is sent to Azure AI Language and Content Safety; Prompt Shields scans document excerpts and assistant questions. Contract chunks, page numbers, opaque owner/project/contract/version IDs, and Ollama-generated vectors are indexed in Azure AI Search. Search queries include server-verified owner, project, and latest-version filters and re-check returned metadata before citations are formed. Translation sends only the selected extracted text or summary to Azure AI Translator.

The application uses only Azure F0/Free APIs and enforces the published monthly service allowances with PostgreSQL counters. Azure quotas may be shared across the subscription and can be consumed by other applications. Operators must provision only supported F0/Free resources, review their regional availability and data-processing terms, and monitor the Azure subscription. Translator's paid native document-translation API is not used. DOCX conversion requires LibreOffice and produces a temporary local PDF; protect the application host and temporary storage.

If Ollama reasoning is enabled, full contract text can be sent to the configured Ollama server for analysis; assistant requests send only the retrieved source passages and question. Ollama embeddings are generated at the configured local endpoint before vectors are sent to Azure AI Search. Review Ollama's access controls and retention practices, and do not expose an unauthenticated Ollama server.

Rate-limit state is stored in PostgreSQL. The client address is taken from the direct ASGI connection; forwarded headers are not trusted.

## Reporting

No monitored security contact has been supplied. Add a private reporting address and coordinated disclosure process before commercial distribution.
