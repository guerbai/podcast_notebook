# Anthropic Proxy Summary Design

## Goal

Replace the podcast summary provider's DeepSeek/OpenAI-compatible request with the LAN proxy's Anthropic Messages API. The service must use the discovered mDNS host, fixed model and effort settings, and must never silently fall back to the OpenAI protocol.

## Provider Contract

- Base URL: `http://MacBook-Work.local:15723`
- Endpoint: `POST /v1/messages`
- Protocol version header: `anthropic-version: 2023-06-01`
- Authentication: `x-api-key`, sourced from `PODCAST_NOTEBOOK_LLM_API_KEY`
- Model: fixed to `kimi-k3`
- Maximum output: `8192` tokens
- Effort: fixed to `output_config.effort=max`
- Mode: non-streaming because the current HTTP API and frontend wait for one complete summary

The existing system prompt becomes the Anthropic top-level `system` field. The `messages` array contains only the user prompt. The response parser concatenates the `text` value of every `content` block whose `type` is `text`.

## Configuration And Secrets

The LAN hostname and timeout remain ordinary project configuration. The access key is read only from the process environment and is removed from YAML configuration, examples, logs, errors, and documentation. The model, maximum token count, API version, and effort are code-level protocol constants so configuration cannot accidentally violate the gateway contract.

There is no OpenAI-compatible fallback. Missing credentials raise the existing not-configured error; network, HTTP, malformed JSON, and empty-text responses raise the provider error.

## Code Shape

`backend/summarizer.py` keeps the existing `SummaryClient` boundary and replaces the OpenAI-compatible implementation with an Anthropic Messages client built on the project's existing `httpx` dependency. Summary prompt construction, language normalization, Markdown normalization, file writing, task events, and database updates remain unchanged.

`backend/config.py` changes the LLM defaults to the LAN proxy and removes YAML API-key/model ownership. The local and example YAML files contain the mDNS base URL and timeout only.

## Verification

Tests will be added incrementally for:

1. Anthropic request URL, headers, top-level system prompt, fixed model, token limit, effort, and non-streaming mode.
2. Concatenating multiple Anthropic text blocks while ignoring non-text blocks.
3. Environment-only credential loading and LAN proxy configuration.
4. Existing summary generation behavior and API error mapping.

Runtime verification runs in this order:

1. Health endpoint returns JSON containing `ok: true`.
2. A request using `effort=banana` returns HTTP 400 and lists the accepted effort values.
3. A real request using `effort=max` and `kimi-k3` returns text content.
4. Relevant and full project tests pass.

Verification output must redact the API key. Any failure stops the migration report; it must not trigger a protocol, model, or effort fallback.
