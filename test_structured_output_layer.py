class MockParser:
    def get_format_instructions(self):
        return "Return JSON schema."

    def parse(self, text):
        if "\\'" in text:
            raise ValueError("Invalid json output")
        return {"parsed": True}


class MockLLM:
    def __init__(self, provider):
        self.model_name = "mock-model"
        self.provider = provider
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1

        class Res:
            pass

        res = Res()
        if self.calls == 1:
            res.content = "{ \"error\": \\'quotes\\' }"  # malformed
        else:
            if "CRITICAL RETRY" in prompt:
                res.content = '{ "success": true }'  # fixed
            else:
                res.content = (
                    "{ \"error\": \\'quotes\\' }"  # still malformed if no prompt update
                )
        return res


def test_wrapper():
    parser = MockParser()
    llm = MockLLM("mistral")
    provider = "mistral"

    class StructuredLLMWrapper:
        def invoke(self, prompt_str):
            if isinstance(prompt_str, str):
                final_prompt = prompt_str + "\n" + parser.get_format_instructions()
            else:
                final_prompt = prompt_str

            current_prompt = final_prompt
            last_error = None
            for attempt in range(3):
                try:
                    res = llm.invoke(current_prompt)
                    content = res.content

                    try:
                        return parser.parse(content)
                    except Exception as e:
                        current_prompt = (
                            final_prompt
                            + f"\n\nCRITICAL RETRY (Attempt {attempt+2}): Your previous response was not valid JSON. The parser error was:\n{e}\n\nReturn ONLY a valid response matching the required schema. Do not escape single quotes as \\'."
                        )
                        last_error = e
                        print(
                            f"CRITICAL PARSE ERROR on Attempt {attempt + 1} | Provider: {provider} | Model: {llm.model_name}\nError: {e}\nSnippet: {content[:100]}"
                        )
                        continue
                except Exception as e:
                    last_error = e
                    continue

            raise last_error

    w = StructuredLLMWrapper()
    res = w.invoke("Hello")
    print("Final result:", res)


if __name__ == "__main__":
    test_wrapper()
