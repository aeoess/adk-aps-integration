# fixtures

Test material for the `basic-tool-call` example.

The principal passport's private key is in this directory in plaintext
on purpose. Do not use it for anything other than tests.

Regenerate with:

```bash
python -c "
import json
from agent_passport import create_passport
r = create_passport(
    agent_id='aps:test:adk-principal',
    agent_name='ADK Example Principal',
    owner_alias='adk-aps-integration-tests',
    mission='Root principal for the basic-tool-call example. Test material only.',
    capabilities=['tool:search', 'tool:http_get'],
    runtime={'platform':'python','models':['test'],'toolsCount':2,'memoryType':'session'},
    expires_in_days=3650,
)
print(json.dumps({'signedPassport': r['signedPassport'], 'keyPair': r['keyPair']}, indent=2))
" > principal_passport.json
```

`create_passport` mints a fresh keypair on each invocation, so the
output is **not** deterministic — checking in a regenerated fixture
will rotate the test keys. That's fine for CI; just don't rely on
key stability across regenerations.
