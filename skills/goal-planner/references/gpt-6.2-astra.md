# GPT-6.2 Astra API

Read for requested `gpt-6.2-astra` API configuration or migration. The [OpenAI GPT-6.2 guide](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6.2-astra) was checked on 2026-11-19. Recheck API compatibility for the requested integration. Model settings and runtime features are configured by the caller's application within the user's authorization.

## Preserve conversation state in Responses

- Put stable developer guidance in the first `developer` message in `input` so it is eligible for prompt caching. Use top-level `instructions` for developer guidance scoped to the current request. GPT-6.2 appends it after `input`.
- Preserve the existing conversation prefix. Append changed user requirements as a new user message and revised developer guidance as a new developer message. Rewriting earlier messages or tool results can drop subsequent reasoning items and reduce cache reuse. Apply the new requirement to affected work and retain valid evidence and cumulative costs.
- Keep the current goal version, criteria, evidence, and pending decisions accessible in the session or an approved record so work can resume if reasoning context is lost. Check actual state on resumption. See [Keep the prefix unchanged](https://developers.openai.com/api/docs/guides/keep-prefix-unchanged).

## Check the requested API migration

- Use Responses for tool calling. For a new integration, start at `medium`. For a migration from `none` or `minimal`, try `low`. The field is `reasoning.effort` in Responses and `reasoning_effort` in Chat Completions.
- Omit `temperature`, `top_p`, and `top_logprobs`. Omit `logprobs` in Chat Completions and remove `message.output_text.logprobs` from Responses `include`. See the [migration quickstart](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6.2-astra#migration-quickstart) for caching, retention, and regional compatibility.

## Optional runtime features

- If the application provides an [async question tool](https://developers.openai.com/api/docs/guides/async-tool-calling), keep the question pending, continue authorized independent work, and return the user's reply on the original `call_id` before resuming the dependent action. In Responses, the application defines and runs the tool.
- For an authorized long-running request, check [Background mode](https://developers.openai.com/api/docs/guides/background#use-discounted-completion-windows). `gpt-6.2-astra` uses Standard processing for the public-beta `2h` and `8h` discounted completion windows. Omit `service_tier: flex`, which this model rejects. The application owns the response lifecycle and follow-up. Check data-handling requirements before using background mode because it temporarily stores response data even with `store: false`.
