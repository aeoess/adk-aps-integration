# fixtures

Deterministic test material for the `basic-tool-call` example.

Do not use these keys for anything other than tests. The principal
passport is derived from a known seed and its private key is in this
directory in plaintext on purpose.

Regenerate with:

```bash
python -c "from agent_passport_system import Passport; \
  p = Passport.create(seed='adk-aps-integration-basic-tool-call'); \
  p.write('principal_passport.json')"
```
