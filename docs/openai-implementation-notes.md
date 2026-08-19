# OpenAI implementation notes

These notes capture the official-documentation baseline used for the first provider implementation.

- Responses API file inputs accept Base64 data, a Files API ID, or an external URL.
- Vision-capable models process PDF extracted text and page images; PDF detail is configurable and
  affects image token usage.
- The Python SDK supports `client.responses.parse(..., text_format=PydanticModel)` and exposes the
  parsed structured result.
- API keys belong in environment variables or a secret-management service, never source or a public
  repository.

Primary sources:

- https://developers.openai.com/api/docs/guides/file-inputs
- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/docs/guides/production-best-practices

The provider must remain model-configurable because model availability and pricing change over
time. Release documentation names only defaults that have been verified at release time.

