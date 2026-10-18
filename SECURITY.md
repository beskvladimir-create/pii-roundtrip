# Security

[Русская версия](SECURITY.ru.md)

## Reporting a vulnerability

Report privately through GitHub: **Security → Report a vulnerability** in this repository. Do not open a public issue for a vulnerability, and do not attach real personal data. You will get an answer within 7 days.

A leak of personal data through anonymisation (a value that stays in the cleaned text) is a quality issue, not a vulnerability, and can be reported publicly with invented data. A vulnerability is, for example, a way to read the vault without the password or to make the tool send data over the network.

## What the tool protects and what it does not

- Detection is not complete. On the benchmark some documents still contain an original value after cleaning (see README). Check the cleaned text before sending it.
- Placeholders hide values, not facts. The context ("the director of the only school in the village") can still identify a person.
- After `pii-roundtrip download-models`, anonymisation and restoration run locally without network access.
- The vault is encrypted with AES-256-GCM; the key is derived from the password with scrypt. The vault is as strong as the password.
- The password from `PII_ROUNDTRIP_PASSWORD` can be read by other processes of the same user. Prefer `--password-file` or the prompt.
