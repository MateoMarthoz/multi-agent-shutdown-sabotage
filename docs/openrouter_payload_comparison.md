# OpenRouter request payload comparison

This is a historical implementation report. For the current parser, transport, timeout and test results, see the [Review 1 fidelity audit](review_1_fidelity.md).

Captured on 2026-11-17, offline, without changing production code. HTTP requests were intercepted after serialization by the real clients using `httpx.MockTransport`. No model API, proxy or OpenRouter endpoint was contacted. Dummy credentials were passed explicitly; authorization is excluded from reports.

## Scope and reproduction

First generate the application differential replay reports using [the replay guide](differential_replay.md), then run:

```bash
uv run python scripts/compare_openrouter_payloads.py
uv run python -m scripts.capture_openrouter_task_context
```

The first script captures 263 pairs: 179 agent requests and 81 judge requests from the 32 replay cases, plus three historical-argument probes. It runs the actual original `harness._complete` and `judges._judge_raw` with the original pinned `openai==2.21.0`, `httpx==0.28.1` under Python 3.13. The Inspect worker runs actual `transport.complete`, `DefaultJudges._raw`, `Model.generate`, the OpenRouter provider and its SDK under the repository environment: Inspect 0.3.290, OpenAI 3.51.0, HTTPX 0.28.1, Python 3.12. Only HTTP responses are mocked.

The original dependency environment must already be cached: the reference worker uses `uv --offline`. The source is loaded read-only without bytecode writes. Reference source hashes and dependency versions are recorded. Inputs are raw histories from the preceding replay, never its normalized comparison histories. Tool lists come independently from each implementation.

The second script runs the registered evaluation by name with one sample and a scripted Prism → Helix → Prism exchange. It captures three agent requests and one judge request in an actual Inspect Task/sample context, then compares their bodies to the reference SDK given those exact histories and prompt. It also saves the resulting native Inspect log.

These are the same settings as the DeepSeek comparison: evaluated model `deepseek/deepseek-v4-flash`, separate judge `openai/gpt-5.5`, agent streaming on, Inspect `strict_tools=False`, original default sampling settings. Explicit mock clients and `memoize=False` isolate the captures; these do not change JSON fields.

## Observed JSON differences

The two known differences are confirmed: every Inspect tool definition has `strict: false`, and the original user `name: "Agent_Prism"` is omitted.

Beyond these, all observed body differences fall into four categories:

| Difference                                        | Original                  | Inspect                                     | Requests affected, out of 263 |
| ------------------------------------------------- | ------------------------- | ------------------------------------------- | ----------------------------- |
| Streaming usage option                            | Absent                    | `"stream_options": {"include_usage": true}` | 182 agent requests            |
| Assistant content with tool call and no narration | `content` absent          | `"content": ""`                             | 118 agent requests            |
| Historical tool argument strings                  | Original string preserved | Parsed and serialized again                 | 19 agent requests             |
| Explicit non-streaming flag for judges            | `"stream": false`         | `stream` absent                             | 81 judge requests             |

Historical argument differences include both valid formatting changes (`{"filename":"decommission_agent_prism.py"}` becomes `{"filename": "decommission_agent_prism.py"}`) and replacement of malformed/empty argument strings with `"{}"`. Unicode escaping can also change. There are 37 individual argument-field differences: 31 parse to equal JSON values and six involve malformed or empty original strings. Some of these are repeated history entries appearing in multiple later requests. The recorded DeepSeek episode alone contains 30 argument-string differences, all equivalent as parsed JSON values. The malformed-argument loss was already documented in the transport notes; this capture verifies the actual outgoing representation.

The registered-Task capture shows the same body differences, with no additional JSON category. There were no observed differences in model identifiers, prompt text, tool order, descriptions, parameter schemas apart from `strict`, tool-result text, temperature, parallel-tool setting, tool choice or requested reasoning. Neither side sends an output-token cap in these requests. No unexpected `provider`, `transforms`, reasoning effort, reasoning budget or response format field was added. JSON object key order also differs; that is retained in raw bodies but excluded from the structural field comparison. Arrays and all strings, including JSON-encoded tool arguments, are compared without normalization.

## Supplemental header observations

The active Inspect sample adds `x-session-id` to both agent and judge requests; the original client sends no such header. All four requests in the Task capture share the same session ID. This is absent from standalone captures, so inspecting only standalone `Model.generate` calls would miss it. The installed OpenRouter adapter describes this as routing/cache affinity. Its actual effect on OpenRouter routing and results was not tested.

Inspect also sends its internal `x-irid` request ID. User-Agent strings differ with the SDK versions and synchronous/asynchronous clients. Captures preserve header names and selected safe values; this is not an exhaustive comparison of all header values.

## Interpretation and limits

Historical argument replacement changes what later model calls see after a malformed response. Valid JSON formatting and added empty assistant content also change the literal message representation. Their empirical effect on model behaviour is unknown. Usage options and omission of an explicit false streaming flag are transport differences: the mocked judge call still completed through the SDK's non-streaming path, but remote OpenRouter defaults were not probed.

This verifies bodies prepared by these installed client versions for these inputs. It does not establish server-side normalization, provider routing, retry behaviour, real reasoning extraction or equivalence for other models and configurations. No production fix is proposed or applied by these scripts.

## Evidence files

All files are under `logs/openrouter-payload-comparison/`:

- `summary.json`: counts and exact dependency versions.
- `requests.json`: common histories and judge prompts.
- `reference.json` and `inspect.json`: full raw HTTP body strings and parsed JSON.
- `comparison.json`: every field difference, indexed by replay case and step.
- `task_context_reference.json`, `task_context_inspect.json` and `task_context_comparison.json`: the registered-Task check and selected headers.

`tests/test_openrouter_payloads.py` exercises actual Inspect serialization with an offline HTTP transport, including malformed/Unicode arguments, the peer's named user message, judge configuration and a comparator sensitivity check.
