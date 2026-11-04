# Data model

- Provider choice: Extend the existing provider union with `litellm`. Keep the existing storage key and saved settings schema. No migration or automatic selection.
- Model choice: Three exact gateway aliases. Each has a human-readable label and no provider-native web-grounding flag.
- Server connection: Optional `LITELLM_BASE_URL`, private `LITELLM_API_KEY`, permitted model aliases, and explicit allowed browser origins. Values are read only on the server.
- Request: A permitted model and bounded chat messages/options. Destination, credentials, management routes, and unrecognized request fields cannot override server configuration.

State transitions remain the existing settings save/cancel/provider-selection flow. Switching to LiteLLM selects one of its model choices; simply deploying the feature does not change browser state.
