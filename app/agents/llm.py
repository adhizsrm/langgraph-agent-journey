import os
import json
import re
from typing import Any, Dict
from dotenv import load_dotenv
from app.state.schemas import (
    OrchestratorOutput,
    GeneratedFiles,
    RepairAnalysis,
    EnhancementAnalysis,
)
from pydantic import ValidationError
import time
from app.telemetry import telemetry_tracker

provider = os.environ.get("LLM_PROVIDER", "mistral").lower()

if provider == "openrouter":
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.environ.get("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet"),
        api_key=os.environ.get("OPENROUTER_API_KEY"),
        base_url=os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        temperature=0.1,
    )
elif provider == "groq":
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        model=os.environ.get("GROQ_MODEL", "llama3-70b-8192"),
        api_key=os.environ.get("GROQ_API_KEY"),
        base_url=os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        temperature=0.1,
    )
else:
    from langchain_mistralai import ChatMistralAI

    llm = ChatMistralAI(
        model=os.environ.get("MISTRAL_MODEL", "mistral-small-latest"), temperature=0.1
    )


class JSONExtractionError(Exception):
    pass


class JSONSyntaxError(Exception):
    pass


class SchemaValidationError(Exception):
    pass


def _extract_and_parse_json(content: str) -> Dict[str, Any]:
    # 1. Strip think blocks cleanly
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

    # 2. Extract block gracefully without string corruption
    candidate = content
    fallback = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if fallback:
        candidate = fallback.group(1)
    else:
        fallback_match = re.search(r'\{\s*"', content)
        if fallback_match:
            start_idx = fallback_match.start()
            last_brace_idx = content.rfind("}")
            if last_brace_idx > start_idx:
                candidate = content[start_idx : last_brace_idx + 1]
            else:
                raise JSONExtractionError("Found starting brace but no ending brace")
        else:
            candidate = content.strip()

    if not candidate.startswith("{"):
        raise JSONExtractionError("No JSON object detected in response")

    # DO NOT BLINDLY STRING REPLACE. We explicitly rely on json.loads throwing a JSONDecodeError if \' is inside avoiding silent source corruption!
    try:
        parsed = json.loads(candidate, strict=False)
        return parsed
    except json.JSONDecodeError as e:
        raise JSONSyntaxError(f"Extracted candidate was not valid JSON syntax: {e}")


def create_structured_llm(pydantic_schema, caller="unknown"):
    if provider == "openrouter":
        try:
            native_llm = llm.with_structured_output(pydantic_schema)

            class NativeStructuredLLMWrapper:
                def invoke(self, prompt_str):
                    current_prompt = prompt_str
                    last_error = None
                    for attempt in range(3):
                        try:
                            # 1. Invoking natively extracts via provider structural tool-calls organically!
                            t0 = time.time()
                            res = native_llm.invoke(current_prompt)
                            latency = time.time() - t0
                            telemetry_tracker.record_llm_call(
                                caller=caller,
                                provider=provider,
                                model=(
                                    llm.model_name
                                    if hasattr(llm, "model_name")
                                    else "unknown"
                                ),
                                latency=latency,
                                input_chars=len(current_prompt),
                                output_chars=len(str(res)),
                                input_tokens=None,
                                output_tokens=None,
                                total_tokens=None,
                                parse_success=True,
                            )
                            return res
                        except Exception as e:
                            model_name = (
                                llm.model_name
                                if hasattr(llm, "model_name")
                                else "unknown"
                            )
                            current_prompt = (
                                prompt_str
                                + f"\n\nCRITICAL RETRY (Attempt {attempt+2}): Your previous response failed structural extraction.\nThe parser error was:\n{e}\n\nReturn ONLY a valid response matching the required schema. Do not escape single quotes inside JSON strings as \\'. Only escape double quotes."
                            )
                            last_error = SchemaValidationError(str(e))
                            print(
                                f"CRITICAL PARSE ERROR on Native LLM Output (Attempt {attempt + 1}) | Provider: {provider} | Model: {model_name}\nError: {e}"
                            )
                            continue
                    raise last_error

            return NativeStructuredLLMWrapper()
        except Exception:
            pass  # Fall back to legacy string parser if with_structured_output crashes statically

    # Manual Parsing Wrapper for Groq / Mistral / Native Failures
    if hasattr(pydantic_schema, "model_json_schema"):
        schema_json = pydantic_schema.model_json_schema()
    else:
        schema_json = pydantic_schema.schema()

    class StructuredLLMWrapper:
        def invoke(self, prompt_str):
            if isinstance(prompt_str, str):
                final_prompt = (
                    prompt_str
                    + "\n\nCRITICAL: You MUST output ONLY valid JSON matching this schema:\n"
                    + json.dumps(schema_json, indent=2)
                    + "\nAbsolutely NO conversational text, NO <think> tags, and NO markdown prefixes before the JSON."
                )
            else:
                final_prompt = prompt_str

            current_prompt = final_prompt
            last_error = None
            for attempt in range(3):
                try:
                    t0 = time.time()
                    res = llm.invoke(current_prompt)
                    latency = time.time() - t0
                    content = res.content

                    input_toks, output_toks, total_toks = None, None, None
                    if (
                        hasattr(res, "response_metadata")
                        and "token_usage" in res.response_metadata
                    ):
                        tu = res.response_metadata["token_usage"]
                        input_toks = tu.get("prompt_tokens")
                        output_toks = tu.get("completion_tokens")
                        total_toks = tu.get("total_tokens")
                    elif hasattr(res, "usage_metadata") and isinstance(
                        res.usage_metadata, dict
                    ):
                        tu = res.usage_metadata
                        input_toks = tu.get("input_tokens")
                        output_toks = tu.get("output_tokens")
                        total_toks = tu.get("total_tokens")

                    try:
                        parsed_dict = _extract_and_parse_json(content)
                    except JSONExtractionError as e:
                        current_prompt = (
                            final_prompt
                            + f"\n\nCRITICAL (Attempt {attempt+2}): JSONExtractionError - No JSON block found. {e}"
                        )
                        last_error = e
                        print(f"JSONExtractionError: Attempt {attempt+1}")
                        telemetry_tracker.record_llm_call(
                            caller=caller,
                            provider=provider,
                            model=getattr(
                                llm, "model", getattr(llm, "model_name", "unknown")
                            ),
                            latency=latency,
                            input_chars=len(current_prompt),
                            output_chars=len(content),
                            input_tokens=input_toks,
                            output_tokens=output_toks,
                            total_tokens=total_toks,
                            parse_success=False,
                            parse_error=str(e),
                        )
                        continue
                    except JSONSyntaxError as e:
                        current_prompt = (
                            final_prompt
                            + f"\n\nCRITICAL (Attempt {attempt+2}): JSONSyntaxError - {e}. Do NOT escape ' as \\'. Only escape \"."
                        )
                        last_error = e
                        print(f"JSONSyntaxError: Attempt {attempt+1} - {e}")
                        telemetry_tracker.record_llm_call(
                            caller=caller,
                            provider=provider,
                            model=getattr(
                                llm, "model", getattr(llm, "model_name", "unknown")
                            ),
                            latency=latency,
                            input_chars=len(current_prompt),
                            output_chars=len(content),
                            input_tokens=input_toks,
                            output_tokens=output_toks,
                            total_tokens=total_toks,
                            parse_success=False,
                            parse_error=str(e),
                        )
                        continue

                    try:
                        validated = pydantic_schema.model_validate(parsed_dict)
                        telemetry_tracker.record_llm_call(
                            caller=caller,
                            provider=provider,
                            model=getattr(
                                llm, "model", getattr(llm, "model_name", "unknown")
                            ),
                            latency=latency,
                            input_chars=len(current_prompt),
                            output_chars=len(content),
                            input_tokens=input_toks,
                            output_tokens=output_toks,
                            total_tokens=total_toks,
                            parse_success=True,
                        )
                        return validated
                    except ValidationError as e:
                        current_prompt = (
                            final_prompt
                            + f"\n\nCRITICAL (Attempt {attempt+2}): SchemaValidationError - {e}"
                        )
                        last_error = SchemaValidationError(f"Schema mismatch: {e}")
                        print(f"SchemaValidationError: Attempt {attempt+1}")
                        telemetry_tracker.record_llm_call(
                            caller=caller,
                            provider=provider,
                            model=getattr(
                                llm, "model", getattr(llm, "model_name", "unknown")
                            ),
                            latency=latency,
                            input_chars=len(current_prompt),
                            output_chars=len(content),
                            input_tokens=input_toks,
                            output_tokens=output_toks,
                            total_tokens=total_toks,
                            parse_success=False,
                            parse_error=str(last_error),
                        )
                        continue

                except Exception as e:
                    last_error = e
                    continue

            raise last_error

    return StructuredLLMWrapper()


# Setup LLM with robust string-based structured output constraints
orchestrator_llm = create_structured_llm(OrchestratorOutput, caller="orchestrator")
backend_llm = create_structured_llm(GeneratedFiles, caller="backend")
frontend_llm = create_structured_llm(GeneratedFiles, caller="frontend")
repair_llm = create_structured_llm(RepairAnalysis, caller="repair")
enhancement_llm = create_structured_llm(EnhancementAnalysis, caller="enhancement")
