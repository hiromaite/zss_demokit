# Documentation Index

This directory contains the requirements, architecture, protocol, backlog,
validation, and release planning documents for `zss_demokit`.

The project has moved beyond early mockups. The top-level firmware and the
PySide6 desktop GUI are both active implementation surfaces, so these documents
serve two purposes:

- define the intended system behavior
- record implementation state, validation results, and remaining decisions

## Status Labels

Use these labels when reading or updating documents:

| Label | Meaning |
| :--- | :--- |
| `Canonical` | Current reference for names, boundaries, or requirements |
| `Active Plan` | Still used to drive upcoming implementation |
| `Validation Log` | Records tested behavior and evidence |
| `Release` | Packaging or user-test procedure |
| `Reference` | Historical or comparative context; useful but not authoritative |
| `Archive Candidate` | Keep for now, but consider moving under `docs/archive/` later |

## Canonical Documents

| Document | Status | Purpose |
| :--- | :--- | :--- |
| `system_requirements.md` | `Canonical` | System scope, constraints, and requirements |
| `system_architecture.md` | `Canonical` | Component boundaries and data flow |
| `design_decisions.md` | `Canonical` | Accepted design decisions |
| `protocol_catalog_v1.md` | `Canonical` | Field names, commands, flags, and capability meanings |
| `communication_protocol.md` | `Canonical` | Shared logical protocol and transport mapping |
| `ble_transport_v1.md` | `Canonical` | BLE GATT / packet behavior |
| `wired_transport_v1.md` | `Canonical` | Wired binary frame behavior |
| `recording_schema.md` | `Canonical` | CSV schema and recording metadata |
| `gui_implementation_spec_v1.md` | `Canonical` | GUI behavior and layout intent |

## Active Plans

| Document | Status | Purpose |
| :--- | :--- | :--- |
| `implementation_backlog_v1.md` | `Active Plan` | Milestones, extension backlog, and current progress |
| `system_usability_review_v1.md` | `Active Plan` | UX / usability review and priority rationale |
| `flow_verification_plan_v1.md` | `Active Plan` | Guided flow verification UX and data model |
| `sampling_ble_flow_integration_plan_v1.md` | `Active Plan` | Sampling, BLE batch, and flow integration sequence |
| `project_organization_review_v1.md` | `Active Plan` | Repository cleanup, naming, and archive decisions |

## Validation And Release

| Document | Status | Purpose |
| :--- | :--- | :--- |
| `validation_checklist_v1.md` | `Validation Log` | GUI / firmware / integration checks and evidence |
| `distribution_plan_v1.md` | `Release` | Beta distribution policy, gate, task order, and tag/artifact flow |
| `release_notes_beta3.md` | `Release` | Beta3 package notes, highlights, known gaps, and distribution checklist |
| `windows_beta_smoke_checklist_v1.md` | `Release` | Windows packaging and user smoke checklist |

## Reference And Historical Context

| Document | Status | Purpose |
| :--- | :--- | :--- |
| `legacy_current_feature_matrix.md` | `Reference` | Old vs current firmware / GUI feature comparison |
| `feature_extension_plan_v1.md` | `Reference` | Bundle-level feature restoration and extension history |
| `active_development_bundles_v1.md` | `Reference` | 2026-05-02 bundle branch plan and outcomes |
| `sampling_architecture_v1.md` | `Reference` | Earlier sampling architecture notes |
| `firmware_implementation_plan_v1.md` | `Archive Candidate` | Initial firmware implementation plan |
| `firmware_worktree_plan_v1.md` | `Archive Candidate` | Earlier worktree / branch workflow note |
| `device_adapter_contract_v1.md` | `Archive Candidate` | Initial GUI adapter contract; superseded in part by current controllers / backend |

## Reading Paths

For normal implementation:

1. `implementation_backlog_v1.md`
2. `system_usability_review_v1.md`
3. `validation_checklist_v1.md`
4. the source files touched by the task

For protocol or CSV changes:

1. `protocol_catalog_v1.md`
2. `communication_protocol.md`
3. `ble_transport_v1.md` or `wired_transport_v1.md`
4. `recording_schema.md`
5. `validation_checklist_v1.md`

For flow calibration / characterization work:

1. `flow_verification_plan_v1.md`
2. `sampling_ble_flow_integration_plan_v1.md`
3. `implementation_backlog_v1.md`
4. `validation_checklist_v1.md`

For packaging / distribution:

1. root `README.md`
2. `gui_prototype/packaging_README.md`
3. `distribution_plan_v1.md`
4. `release_notes_beta3.md`
5. `windows_beta_smoke_checklist_v1.md`
6. `validation_checklist_v1.md`

## Update Policy

- Update the relevant design or backlog document in the same change as the
  implementation when behavior changes.
- Update `validation_checklist_v1.md` whenever a new smoke, probe, or manual
  test becomes part of the expected verification path.
- Preserve historical documents until they are explicitly moved to an archive
  folder. Stale information should be labeled, not silently deleted.
- Keep `GasSensor-Proto` as the preferred device name in new docs. Mention
  `M5STAMP-MONITOR*` only as a legacy-compatible scan target.
