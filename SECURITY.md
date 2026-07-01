# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Report them privately via GitHub's [security advisories](https://github.com/BioLM/biolm-hub/security/advisories/new)
or by email to **support+security@biolm.ai**.
Include enough detail to reproduce the issue. We'll acknowledge your report, keep you updated on the
fix, and credit you (if you'd like) once it's resolved.

## Scope

This project deploys models to **your own** Modal workspace and, optionally, reads/writes weights and
cached responses in **your own** object storage. Most relevant concerns:

- **Credentials.** Modal tokens and R2/object-storage credentials are supplied by you via Modal
  secrets and environment variables — never commit them. The default public model bucket is
  read-only.
- **Untrusted inputs.** Model endpoints accept sequence/structure inputs; report any input that can
  cause unsafe behavior beyond the intended inference.
- **Supply chain.** Dependencies are pinned. Flag any dependency or model-weight source you believe
  is compromised.

## Model weights & licenses

Each model carries its own upstream license (see its directory's `sources.yaml` and `LICENSE`). If you
believe a model is included under an incompatible or misattributed license, please report it the same
way — we treat license issues as security-adjacent.
