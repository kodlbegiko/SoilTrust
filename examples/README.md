# Example outputs

Run:

```bash
PYTHONPATH=src python -m soiltrust.cli --lat 24.1236 --lon 120.6753 --weather fixture
```

The included offline fixture is expected to `ABSTAIN` because both the soil and weather records are explicitly synthetic demo evidence. This is a feature, not a failed demo: it demonstrates that the pipeline will not convert placeholders into confident recommendations.
