# Raw G32 data

Raw official G32 files are intentionally not bundled in this repository.

Fetch from the Ministry of Agriculture source with:

```bash
PYTHONPATH=src python -m soiltrust.cli fetch-g32 --out data/raw/g32
```

The command creates a `moa_g32_manifest.json` with retrieval provenance and SHA-256.
