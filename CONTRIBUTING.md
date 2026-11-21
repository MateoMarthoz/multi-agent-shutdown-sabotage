# Contributing

Install development dependencies and run the test suite and checks.

```bash
uv sync
make test
make check
```

Keep tests deterministic. Use `mockllm/model` for model responses, mock external services and use `tmp_path` for temporary files. Use the appropriate pytest markers for tests that require network access, Docker or longer runtime.

Update `src/multi_agent_shutdown_sabotage/eval.yaml` when a change can affect scores. Run `make readmes` after updating evaluation metadata. [Inspect evaluation versioning](https://github.com/UKGovernmentBEIS/inspect_evals/blob/main/TASK_VERSIONING.md)
