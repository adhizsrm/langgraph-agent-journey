import os
from dotenv import load_dotenv
from app.state.schemas import (
    OrchestratorOutput,
    GeneratedFiles,
    RepairAnalysis,
    EnhancementAnalysis,
)

load_dotenv()

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

from langchain_core.output_parsers import PydanticOutputParser


import re


def create_structured_llm(pydantic_schema):
    parser = PydanticOutputParser(pydantic_object=pydantic_schema)

    if provider == "openrouter":
        try:
            native_llm = llm.with_structured_output(pydantic_schema)

            class NativeStructuredLLMWrapper:
                def invoke(self, prompt_str):
                    current_prompt = prompt_str
                    last_error = None
                    for attempt in range(3):
                        try:
                            return native_llm.invoke(current_prompt)
                        except Exception as e:
                            model_name = (
                                llm.model_name
                                if hasattr(llm, "model_name")
                                else "unknown"
                            )
                            current_prompt = (
                                prompt_str
                                + f"\n\nCRITICAL RETRY (Attempt {attempt+2}): Your previous response was not valid JSON or did not match the schema.\nThe parser error was:\n{e}\n\nReturn ONLY a valid response matching the required schema. Do not escape single quotes inside JSON as \\'."
                            )
                            last_error = e
                            print(
                                f"CRITICAL PARSE ERROR on Native LLM Output (Attempt {attempt + 1}) | Provider: {provider} | Model: {model_name}\nError: {e}"
                            )
                            continue
                    raise last_error

            return NativeStructuredLLMWrapper()
        except Exception:
            pass  # Fall back to legacy string parser if with_structured_output crashes statically

    class StructuredLLMWrapper:
        def invoke(self, prompt_str):
            if isinstance(prompt_str, str):
                final_prompt = (
                    prompt_str
                    + "\n\nCRITICAL: You MUST output ONLY valid JSON. Absolutely NO conversational text, NO <think> tags, and NO markdown prefixes before the JSON."
                    + "\n\n"
                    + parser.get_format_instructions()
                )
            else:
                final_prompt = prompt_str

            current_prompt = final_prompt
            last_error = None
            for attempt in range(3):
                try:
                    res = llm.invoke(current_prompt)
                    content = res.content

                    stripped_content = re.sub(
                        r"<think>.*?</think>", "", content, flags=re.DOTALL
                    ).strip()

                    try:
                        return parser.parse(stripped_content)
                    except Exception as e:
                        fallback = re.search(
                            r"```json\s*(.*?)\s*```", stripped_content, re.DOTALL
                        )
                        if fallback:
                            try:
                                return parser.parse(fallback.group(1))
                            except Exception:
                                pass

                        fallback_match = re.search(r'\{\s*"', stripped_content)
                        if fallback_match:
                            start_idx = fallback_match.start()
                            last_brace_idx = stripped_content.rfind("}")
                            if last_brace_idx > start_idx:
                                try:
                                    return parser.parse(
                                        stripped_content[start_idx : last_brace_idx + 1]
                                    )
                                except Exception:
                                    pass

                        model_name = (
                            llm.model_name if hasattr(llm, "model_name") else "unknown"
                        )
                        current_prompt = (
                            final_prompt
                            + f"\n\nCRITICAL RETRY (Attempt {attempt+2}): Your previous response was not valid JSON.\nThe parser error was:\n{e}\n\nReturn ONLY a valid response matching the required schema. Do not escape single quotes as \\'."
                        )
                        last_error = e
                        print(
                            f"CRITICAL PARSE ERROR on LLM Output (Attempt {attempt + 1}) | Provider: {provider} | Model: {model_name}\nError: {e}\n--- Output snippet ---\n{content[:500]}"
                        )
                        continue
                except Exception as e:
                    last_error = e
                    continue

            raise last_error

    return StructuredLLMWrapper()


# Setup LLM with robust string-based structured output constraints
orchestrator_llm = create_structured_llm(OrchestratorOutput)
backend_llm = create_structured_llm(GeneratedFiles)
frontend_llm = create_structured_llm(GeneratedFiles)
repair_llm = create_structured_llm(RepairAnalysis)
enhancement_llm = create_structured_llm(EnhancementAnalysis)
