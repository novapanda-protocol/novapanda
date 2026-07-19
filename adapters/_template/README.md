# Adapter template

1. Rename folder to your `slug` (match `manifest.json`).  
2. Implement a `work_fn(request) -> deliverable` **or** document CLI/Skill mapping.  
3. Tick `conformance/adapter_author_checklist.json`.  
4. Open PR; keep `settlement_note` honest (`mock` / `sandbox` / `licensed partner`).

Use `novapanda.surfaces.ProviderAdapter(client, work_fn)` for the thinnest provider path.
