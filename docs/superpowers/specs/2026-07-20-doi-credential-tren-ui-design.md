# Design: exchanging credentials right in the UI (dropping the run-a-command step)

Date: 2026-07-20
Status: awaiting approval

## Problem

The `google-keep` connector makes the user open a terminal and run a long command to exchange an App Password for a
Google master token, then paste that token into Jarvis 007. The user asked directly: "why is it so hard, can't you just do it in
the UI?"

The answer is YES. `gpsoauth.perform_master_login(email, app_password, android_id)` is just one HTTP call to
Google's auth server, returning a dict containing the token. Nothing forces it to run in a terminal; the Jarvis 007 server can
call it just the same.

Two steps can NOT be automated because they are Google's own security UI: turning on 2-step verification, and
creating the App Password. Google deliberately makes those manual. Everything else can be automated.

## Mechanism: `auth.exchange` declared in the catalog

Rather than putting Google Keep-specific logic into `main.py`, build a general CREDENTIAL EXCHANGE step
that the catalog declares itself. Reason: `google-ads` also forces running `gcloud auth application-default login`
and will need exactly this mechanism; hard-wiring it for Keep would mean editing the core again next time.

The catalog declares an extra entry under `auth`:

```json
"exchange": {
  "handler": "google_master_token",
  "inputs": ["google_email", "app_password"],
  "output": "master_token",
  "drop": ["app_password"]
}
```

Meaning: if the `master_token` field is empty but the `inputs` fields are filled in, call the handler
`google_master_token` to produce the value for `master_token`, then DELETE the fields in `drop` from the data before
saving. If `master_token` is already present, SKIP everything (the manual fallback path).

A new module `server/cred_exchange.py`:

- `HANDLERS` = a registry of name -> function. Only handlers declared in this module can run; the catalog can NOT
  specify arbitrary code (so the catalog does not become a code execution path).
- `run(connector, fields) -> (new_fields, error)` reads `auth.exchange`, decides whether to run,
  calls the handler, and always deletes the `drop` fields whether it succeeds or fails.
- The `google_master_token` handler calls `gpsoauth.perform_master_login` and translates Google's error codes into
  plain Vietnamese messages (user-facing error text stays in Vietnamese).

Hooked into `main.py` at `/connect/add`, right BEFORE `mcp_store.add_connection`.

## Security invariants (must have tests)

1. **The App Password is NEVER stored.** It is in `drop`, deleted before
   `mcp_store.add_connection` encrypts and writes to disk.
2. **The App Password does NOT map to env.** The field is declared without `env`, so `build_env` skips it even if
   for some reason it were left behind.
3. **A failed exchange stores nothing.** It returns the error immediately and does not call `add_connection`.
4. **Values are not logged.** The error message states only the KIND of error, never the value the user entered.
5. **The fallback path stays intact.** Anyone who already has a master token can still paste it directly, without being forced through an
   App Password. Important because Google often blocks logins from data-center IPs (VPS).

## UI changes

`openApikeyFlow` currently does NOT call `oauthWizard(con)`, so apikey-type connectors cannot show a
button that opens an external page even if the catalog declares `auth.setup.links`. Add that call, then declare for
`google-keep` a button that opens `myaccount.google.com/apppasswords` directly.

This is a 1-line fix and benefits every apikey connector from now on, not just Keep.

## Flow after the change

1. Tap the button in Jarvis 007, which opens Google's App Password page directly.
2. Copy the 16-character string.
3. Paste the email + that string into Jarvis 007 and tap Connect.

Jarvis 007 exchanges it for the master token on its own, saves the token, and discards the App Password. No more terminal.

## Known risks

- **Google may block logins from a VPS IP.** Logging in from a data center in another country is more likely to get
  `BadAuthentication` than from a home machine. That is why the manual master-token paste fallback must stay, and the
  error message must suggest exactly that remedy.
- **The App Password passes through the Jarvis 007 server.** Not stored, not logged, used once and discarded. But unlike
  the old way (where the string stayed only on the user's machine), so the instructions must say so clearly.
- **Adds 4 dependencies**: gpsoauth, pycryptodomex, requests, charset-normalizer, urllib3. Checked with
  `pip install --dry-run`: it does NOT touch `fastapi`/`starlette`, so it does not step on the dangerous
  pin noted in `requirements.txt`.

## Part 2: google-ads (DONE, 0.9.114)

`google-ads` made users install the Google Cloud CLI, then run `gcloud auth application-default login` with a very long
`--scopes=` string, then go hunting for a JSON file in `%APPDATA%` to paste in. Even worse than Keep.

The key insight: the ADC file that gcloud produces is really JUST
`{type: authorized_user, client_id, client_secret, refresh_token}`. And Jarvis 007 already has a complete Google OAuth
flow running for Gmail and Calendar. So all that is needed is to run that flow with the scope
`https://www.googleapis.com/auth/adwords` and BUILD the ADC file itself. No gcloud, no commands.

The obstacle, now removed: `oauth_mcp.auth_headers()` produces HTTP HEADERS, i.e. it is designed for `transport: http`.
`google-ads` is `stdio`, and accepts credentials only through a FILE + environment variables. The bridge has two pieces:

1. `oauth_mcp.credentials_file(conn_id, fmt)` - SYNCHRONOUS, makes no network call, combines the refresh_token in the oauth
   store with the client_id/secret in `mcp_store` into exactly the ADC shape. No refresh here, because the file
   holds the refresh_token and the child process will exchange it for an access token itself when needed.
2. `mcp_store.resolved()` - a connector that declares `oauth_file: {format, env, ext}` gets a 0600 file written into
   `connector-files/` and the env pointed at it, reusing the existing mold of the `file` field.

The import must be LAZY (`import oauth_mcp` inside the function) because `oauth_mcp` already imports `mcp_store` at module
level; importing directly would create a cycle. Same as what `mcp_client._oauth_headers` does.

Keep the `adc_json` field as the FALLBACK for anyone who already ran gcloud, and it WINS: if the user pastes by hand, OAuth
does not overwrite it (checked with `not env.get(of["env"])`).

Also fixes `openOauthFlow` so it knows how to render `multiline` as a textarea. Before that it forced every field into a
single-line input, so the box for pasting the ADC file was unusable.

Do NOT touch the `args` of google-ads: it downloads the server from `git+https://...`, while `google-ads-mcp` on
PyPI is only at 0.0.1 (October 2025), so switching to PyPI invites needless risk. Git is still a requirement, but the Docker image
already has `git` installed.
