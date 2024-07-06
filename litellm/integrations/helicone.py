#### What this does ####
#    On success, logs events to Helicone
import dotenv, os
import requests  # type: ignore
import litellm
import traceback
from litellm._logging import verbose_logger


class HeliconeLogger:
    # Class variables or attributes
    helicone_model_list = ["gpt", "claude", "command-r", "command-r-plus", "command-light", "command-medium", "command-medium-beta", "command-xlarge-nightly", "command-nightly	"]

    def __init__(self):
        # Instance variables
        self.provider_url = "https://api.openai.com/v1"
        self.key = os.getenv("HELICONE_API_KEY")

    def claude_mapping(self, model, messages, response_obj):
        from anthropic import HUMAN_PROMPT, AI_PROMPT

        prompt = f"{HUMAN_PROMPT}"
        for message in messages:
            if "role" in message:
                if message["role"] == "user":
                    prompt += f"{HUMAN_PROMPT}{message['content']}"
                else:
                    prompt += f"{AI_PROMPT}{message['content']}"
            else:
                prompt += f"{HUMAN_PROMPT}{message['content']}"
        prompt += f"{AI_PROMPT}"
        claude_provider_request = {"model": model, "prompt": prompt}

        claude_response_obj = {
            "completion": response_obj["choices"][0]["message"]["content"],
            "model": model,
            "stop_reason": "stop_sequence",
        }

        return claude_provider_request, claude_response_obj
    
    @staticmethod
    def add_metadata_from_header(litellm_params: dict, metadata: dict) -> dict:
        """
        Adds metadata from proxy request headers to Helicone logging if keys start with "helicone_"
        and overwrites litellm_params.metadata if already included.

        For example if you want to add custom property to your request, send
        `headers: { ..., helicone-property-something: 1234 }` via proxy request.
        """
        if litellm_params is None:
            return metadata

        if litellm_params.get("proxy_server_request") is None:
            return metadata

        if metadata is None:
            metadata = {}

        proxy_headers = (
            litellm_params.get("proxy_server_request", {}).get("headers", {}) or {}
        )

        for metadata_param_key in proxy_headers:
            if metadata_param_key.startswith("helicone_"):
                trace_param_key = metadata_param_key.replace("helicone_", "", 1)
                if trace_param_key in metadata:
                    verbose_logger.warning(
                        f"Overwriting Helicone `{trace_param_key}` from request header"
                    )
                else:
                    verbose_logger.debug(
                        f"Found Helicone `{trace_param_key}` in request header"
                    )
                metadata[trace_param_key] = proxy_headers.get(metadata_param_key)

        return metadata

    def log_success(
        self, model, messages, response_obj, start_time, end_time, print_verbose, kwargs
    ):
        # Method definition
        try:
            print_verbose(
                f"Helicone Logging - Enters logging function for model {model}"
            )
            litellm_params = kwargs.get("litellm_params", {})
            litellm_call_id = kwargs.get("litellm_call_id", None)
            metadata = (
                litellm_params.get("metadata", {}) or {}
            )
            metadata = self.add_metadata_from_header(litellm_params, metadata)
            model = (
                model
                if any(
                    accepted_model in model
                    for accepted_model in self.helicone_model_list
                )
                else "gpt-3.5-turbo"
            )
            provider_request = {"model": model, "messages": messages}
            if isinstance(response_obj, litellm.EmbeddingResponse) or isinstance(
                response_obj, litellm.ModelResponse
            ):
                response_obj = response_obj.json()

            if "claude" in model:
                provider_request, response_obj = self.claude_mapping(
                    model=model, messages=messages, response_obj=response_obj
                )

            providerResponse = {
                "json": response_obj,
                "headers": {"openai-version": "2020-10-01"},
                "status": 200,
            }

            # Code to be executed
            url = "https://api.hconeai.com/oai/v1/log"
            if model.startswith("command"):
                url = "https://api.hconeai.com/custom/v1/log"
            headers = {
                "Authorization": f"Bearer {self.key}",
                "Content-Type": "application/json",
            }
            start_time_seconds = int(start_time.timestamp())
            start_time_milliseconds = int(
                (start_time.timestamp() - start_time_seconds) * 1000
            )
            end_time_seconds = int(end_time.timestamp())
            end_time_milliseconds = int(
                (end_time.timestamp() - end_time_seconds) * 1000
            )
            data = {
                "providerRequest": {
                    "url": self.provider_url,
                    "json": provider_request,
                    "meta": {"Helicone-Auth": f"Bearer {self.key}"},
                },
                "providerResponse": providerResponse,
                "timing": {
                    "startTime": {
                        "seconds": start_time_seconds,
                        "milliseconds": start_time_milliseconds,
                    },
                    "endTime": {
                        "seconds": end_time_seconds,
                        "milliseconds": end_time_milliseconds,
                    },
                },  # {"seconds": .., "milliseconds": ..}
            }
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                print_verbose("Helicone Logging - Success!")
            else:
                print_verbose(
                    f"Helicone Logging - Error Request was not successful. Status Code: {response.status_code}"
                )
                print_verbose(f"Helicone Logging - Error {response.text}")
        except:
            print_verbose(f"Helicone Logging Error - {traceback.format_exc()}")
            pass
