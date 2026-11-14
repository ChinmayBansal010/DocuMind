# Security & Data Handling

_Last updated: 14 November 2026_

## Intended deployment
This release has no user accounts, authentication or multi-user isolation. It is designed for one person on a trusted local device, not public hosting or shared access.

## Credentials
Azure keys are read by the Python backend from server-side environment variables. Never place secrets in frontend source, Vite variables, browser storage or version control.

## Local data
Uploaded files and SQLite data are not encrypted by this application. Use a protected OS account, full-disk encryption, secure backups and restrictive file permissions.

## Network exposure
The supplied Docker configuration binds the web application to loopback. Do not expose the service to a network until authentication, authorization, tenant isolation, rate limiting, CSRF protections, monitoring and security review are implemented. Do not expose Ollama's listening port to untrusted networks.

## Vulnerability reporting
A monitored security contact and coordinated disclosure process have not yet been supplied. Add them before public commercial release.
