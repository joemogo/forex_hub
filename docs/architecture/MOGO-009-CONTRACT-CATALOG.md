# MOGO-009 — Contract Catalog

**Milestone:** MOGO-009 Step 2 · **Status:** **APPROVED** (2026-08-07, Step 2A), non-executable · **Date:** 2026-08-07
**Governing document:** [`AUTOMATION_PLATFORM_CONSTITUTION.md`](../governance/AUTOMATION_PLATFORM_CONSTITUTION.md) v1.0 — senior to this catalog
**Specification:** [`MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md`](MOGO-009-AUTOMATION-PLATFORM-ARCHITECTURE.md) · **Decisions:** [ADR-012](../adr/ADR-012-automation-platform-architecture.md)

**This is a tabular catalog, not executable schema.** No JSON Schema file, validator, or runtime type
is created. Field names, types and vocabularies are proposals for Step 3.

Conventions: `sha256` = 64-char lowercase hex · `uuid` = UUIDv4 · `iso8601` = UTC, millisecond
precision · **R** = required, **O** = optional.

---

## A. Command contract

Imperative, rejectable, exactly one per accepted task.

| Field | Type | R/O | Notes |
|---|---|---|---|
| `commandId` | uuid | R | opaque |
| `commandType` | enum | R | see §J |
| `commandVersion` | semver-major int | R | additive-only within major |
| `workflowId` | uuid | R | owning workflow |
| `taskId` | uuid | O | present once a task exists |
| `correlationId` | uuid | R | constant across the whole workflow |
| `causationId` | uuid | R | id of the event/command that caused this |
| `idempotencyKey` | sha256 | R | §I composition; stable across retries |
| `issuedAt` | iso8601 | R | |
| `issuedBy` | string | R | `operator:<id>` \| `orchestrator` \| `workflow:<type>` |
| `targetCapability` | string | R | must exist in the worker registry |
| `inputRefs` | array<ref> | R | identifiers only — **never inline payloads** |
| `policyContext` | object | R | `{authorizationId, policyVersion, permittedOperations[]}` |
| `priority` | int 0–9 | O | default 5 |
| `attemptLimit` | int | O | default 3 |
| `timeoutMs` | int | O | default per capability |
| `approvalRequirements` | array<enum> | O | review types that must clear first |
| `payloadHash` | sha256 | R | over the canonical payload |

**Lifecycle:** `issued → validated → {accepted | rejected}`.
**Validation:** schema version known · identifiers well-formed · `idempotencyKey` present ·
`targetCapability` registered · `policyContext` resolvable · `payloadHash` matches payload.
**A hash mismatch is a rejection, and the rejection is an event.**

## B. Event contract

Immutable fact. Never updated, never deleted.

| Field | Type | R/O | Notes |
|---|---|---|---|
| `eventId` | uuid | R | |
| `eventType` | enum | R | see §J |
| `eventVersion` | int | R | |
| `workflowId` | uuid | R | |
| `taskId` | uuid | O | absent for workflow-level events |
| `correlationId` | uuid | R | |
| `causationId` | uuid | R | |
| `producer` | string | R | `worker:<id>` \| `orchestrator` \| `policyGate` \| `reviewGate` |
| `producerVersion` | semver | R | |
| `occurredAt` | iso8601 | R | when the fact happened |
| `recordedAt` | iso8601 | R | when it was appended |
| `subjectRefs` | array<ref> | R | sources/artifacts/candidates this concerns |
| `payload` | object | R | type-specific |
| `payloadHash` | sha256 | R | |
| `priorEventId` | uuid | O | previous event for the same subject |
| `policyContext` | object | O | present on acquisition-related events |
| `executionResult` | enum | O | `success` \| `failure` \| `partial` |
| `errorClass` | enum | O | §K; required when `executionResult=failure` |
| `sequence` | int | R | monotonic within `workflowId` |

**Ordering:** total within a workflow via `sequence`; across workflows only `recordedAt` is
meaningful. **Duplicate detection:** `(eventType, idempotencyKey, subjectRefs)` — a repeat is
recorded once and flagged. **Corruption detection:** each append records the prior event's
`eventId`, forming a per-workflow chain; a break is detectable on replay.

**Schema evolution:** additive-only within a major version · new fields optional · never remove or
repurpose · consumers ignore unknown fields · breaking change = **new event type**.

## C. Task contract

| Field | Type | Notes |
|---|---|---|
| `taskId` | uuid | unit of retry, claim and idempotency |
| `taskType` | enum | 1:1 with a worker capability |
| `workflowId` | uuid | owner |
| `inputs` / `expectedOutputs` | array<ref> | references only |
| `workerCapability` | string | must be registered |
| `dependsOn` | array<taskId> | must all be `succeeded` |
| `retryPolicy` | object | `{attemptLimit, backoffBaseMs, backoffMultiplier, jitter, retryableClasses[]}` |
| `timeoutPolicy` | object | `{executionTimeoutMs, leaseTtlMs}` |
| `cancellationPolicy` | enum | `cooperative` \| `immediate` |
| `concurrencyKey` | string | at most one running task per key |
| `rateLimitKey` | string | usually `connectorId` |
| `idempotencyKey` | sha256 | §I |
| `reviewRequirements` | array<enum> | blocking review types |
| `state` | enum | §L |
| `attempt` / `leaseHolder` / `leaseExpiresAt` | int / string / iso8601 | claim bookkeeping |

**Terminal states:** `succeeded`, `dead_lettered`, `suppressed`, `cancelled`. Late transitions into a
terminal task are logged as anomalies and **not applied**.

## D. Workflow contract

| Field | Notes |
|---|---|
| `workflowId` / `workflowType` / `workflowVersion` | identity |
| `stateMachine` | declared states + legal transitions |
| `dependencies` | task DAG (acyclic; validated at definition time) |
| `commandsIssued` / `eventsConsumed` | declared surface |
| `compensation` | per-step recovery; **compensation is forward-only** — no destructive rollback of raw artifacts |
| `approvalGates` | states that block on review |
| `suppressionBehavior` | how a suppressed workflow terminates and what remains visible |
| `completionCriteria` / `failureCriteria` | explicit, not inferred |

## E. Worker contract

| Field | Notes |
|---|---|
| `workerId` / `workerVersion` | composite id, semver |
| `capabilities[]` | what it can do |
| `acceptedCommandTypes[]` / `emittedEventTypes[]` | **exhaustive** — emitting an undeclared event is a contract violation |
| `deterministicInputs` | bool; if true, same input must yield same `outputHash` |
| `idempotencyResponsibilities` | which keys it honours |
| `resourceLimits` | wall clock, memory, disk, max artifact bytes |
| `secretScope[]` | `secretRef` names it may resolve — nothing else |
| `connectorScope[]` | connectors it may invoke |
| `outputRestrictions[]` | contexts it may write; **never 10, 13, 14** |
| `healthReporting` | heartbeat interval, last-seen |
| `failureReporting` | must map every failure to an §K class |
| `sandbox` | subprocess isolation; no ambient network in tests |

**A worker may never invoke another worker.**

## F. Connector contract

| Field | Notes |
|---|---|
| `connectorId` / `connectorVersion` | identity; version participates in idempotency keys |
| `supportedSourceTypes[]` / `supportedOperations[]` | `discover` \| `metadata` \| `transcript` \| `artifact` |
| `authRequirements` | `none` \| `apiKey` \| `oauth`; resolved by `secretRef` only |
| `licensingPolicyIntegration` | **mandatory**; receives `authorizationId` + permitted operations |
| `rateLimits` | declared requests/interval and concurrency |
| `pagination` / `checkpointing` / `resumability` | cursor model; checkpoint after each page |
| `rawResponsePreservation` | **mandatory** — raw bytes stored before any parsing |
| `errorClassification` | maps source errors to §K |
| `mutationDetection` | re-fetch hash comparison → `SourceMutationDetected` |
| `fixtures` / `testDoubles` | recorded responses required for: success, 404, 429, auth failure, mutated, partial |
| `capabilityManifest` | machine-readable, validated at registration |

**No connector may override the policy gate.** An out-of-scope operation fails `policy_blocked`.

## G. Artifact contract — states and lineage

| State | Identity | Parent | Immutable |
|---|---|---|---|
| DiscoveredSource | `candidateId` composite | — | no |
| RegisteredSource | `sourceId` composite | candidate | no (versioned) |
| RawArtifact | `artifactId` = `sha256(bytes)` | source | **yes** |
| NormalizedArtifact | `sha256` | raw | yes |
| CleanedArtifact | `sha256` | normalized | yes |
| Segment | `segmentId` = `sha256(parent+offsets)` | cleaned | yes |
| MetadataRecord | `sha256` | segment/artifact | yes |
| DuplicateCandidate | `duplicateDecisionId` | group members | decisions append-only |
| EvidenceCandidate | `evidenceCandidateId` | segment | yes until reviewed |

**Every derived object records:** `parentId`, `transformationId`, `transformationVersion`,
`inputHash`, `outputHash`, `workerId`, `workflowId`, `producedAt`.
**Lineage rule:** child `inputHash` **must equal** parent `outputHash`. A mismatch is a hard error.

## H. Identifier model

| Identifier | Class | Composition |
|---|---|---|
| `workflowId`, `taskId`, `commandId`, `eventId`, `correlationId`, `reviewId` | opaque random | UUIDv4 |
| `causationId` | derived reference | id of the causing event/command |
| `idempotencyKey`, `payloadHash` | content-derived | sha256, §I |
| `artifactId`, `segmentId` | content-derived | sha256 of bytes / parent+offsets |
| `sourceId` | composite human-readable | `SRC\|<platform>\|<normalizedUrlHash12>` |
| `educatorId` | composite human-readable | `EDU\|<slug>` |
| `connectorId` | composite | `CONN\|<sourceType>\|<name>` |
| `workerId` | composite | `WRK\|<capability>` |
| `transformationId` | composite | `XF\|<name>` |
| `duplicateDecisionId`, `evidenceCandidateId` | composite + hash | `DUP\|…`, `EVC\|…` |
| `canonicalRuleId` | composite | `RULE\|<educator>\|<slug>` |
| `hypothesisId`, `evidencePackageId`, `replayPackageId` | **existing — referenced only** | owned by governance; the platform never mints these |

**Collision handling.** Content-derived: identical hash = identical object; identical hash with
differing bytes is a corruption alarm. Opaque: generated with a uniqueness check; a duplicate is a
hard failure. Composite: a collision indicates a genuine identity conflict → human review.

**Reuse verdict.** SHA-256 canonicalization discipline **adapted** into a new namespace.
`alexGStableHash` (64-bit FNV, non-cryptographic), decision-event ids, and `sourceTradeId` are **not
reused** — importing them would couple automation to trading.

## I. Idempotency matrix

| Operation | Key composition | Duplicate | Partial completion | Retry safe | Source mutation |
|---|---|---|---|---|---|
| Source discovery | `(connectorId, query, window)` | return prior | resume cursor | yes | n/a |
| Source registration | `(normalizedUrl, educatorId)` | return existing `sourceId` | n/a | yes | new version |
| Metadata acquisition | `(sourceId, connectorVersion)` | return cached | re-fetch | yes | `SourceMutationDetected` |
| Artifact acquisition | `(sourceId, locator, connectorVersion)` | **no second artifact** | resume from checkpoint | yes | new version, never overwrite |
| Transcript acquisition | as artifact | as artifact | resume | yes | as artifact |
| Raw storage | `(sha256)` | content-addressed no-op | temp+rename | yes | new object |
| Normalize / clean / segment / extract | `(inputHash, transformationId, transformationVersion)` | return existing `outputHash` | re-run stage | yes | parent change → re-run |
| Duplicate analysis | `(candidateSetHash, algorithmVersion)` | recompute allowed | n/a | yes | re-evaluate |
| Evidence-candidate creation | `(segmentId, extractorVersion)` | one per key | n/a | yes | re-evaluate |
| Review request | `(subjectId, reviewType)` | dedupe into open request | n/a | yes | new request |

**Output verification:** every stage re-hashes its output and compares to the recorded `outputHash`.
**Conflict:** two differing outputs for one key = determinism violation → dead-letter and alert;
never pick a winner.

## J. Command and event vocabulary — *conceptual*

**Commands:** `RequestSourceDiscovery` · `RegisterSource` · `EvaluateSourcePolicy` ·
`AcquireSourceMetadata` · `AcquireArtifact` · `AcquireTranscript` · `NormalizeArtifact` ·
`SegmentArtifact` · `ExtractMetadata` · `AnalyzeDuplicates` · `CreateEvidenceCandidate` ·
`RequestHumanReview` · `RecordReviewDecision` · `RetryTask` · `CancelTask` · `SuppressWorkflow` ·
`ReclaimTask`.

**Events:** `SourceDiscoveryRequested` · `SourceDiscovered` · `SourceRegistered` · `PolicyEvaluated` ·
`AcquisitionAuthorized` · `AcquisitionDenied` · `ArtifactAcquisitionRequested` · `ArtifactAcquired` ·
`ArtifactAcquisitionFailed` · `TranscriptAcquired` · `RawArtifactRegistered` · `ArtifactNormalized` ·
`ArtifactSegmented` · `MetadataExtracted` · `DuplicateCandidateDetected` · `EvidenceCandidateCreated`
· `HumanReviewRequired` · `HumanReviewCompleted` · `SourceMutationDetected` · `TaskClaimed` ·
`TaskReclaimed` · `TaskRetryScheduled` · `TaskSucceeded` · `TaskFailed` · `TaskDeadLettered` ·
`WorkflowStarted` · `WorkflowCompleted` · `WorkflowFailed` · `WorkflowSuppressed` ·
`CheckpointVerified` · `CheckpointInvalidated` · `PartialArtifactQuarantined` ·
`RecoveryOverrideIssued` · `SecretAccessed`.

**Not finalized.** Names and payloads are Step 3 work.

## K. Error classification

| Class | Retryable | Terminal | Routes to review |
|---|---|---|---|
| `transient` | ✅ | no | no |
| `rate_limited` | ✅ (backoff) | no | no |
| `dependency_unavailable` | ✅ | no | no |
| `authentication` | ❌ | yes | yes |
| `policy_blocked` | **❌ never** | yes | yes |
| `not_found` | ❌ | yes | no |
| `source_mutated` | ❌ | no | yes |
| `validation` | ❌ | yes | no |
| `deterministic_processing` | ❌ | yes | yes |
| `corrupted_input` | ❌ | yes | yes |
| `human_review_required` | ❌ | no | yes |
| `permanent` | ❌ | yes | no |

Retrying a `policy_blocked` failure is an attempt to launder a denial and is prohibited.

## L. Task state transitions

| From | To | Authority | Condition |
|---|---|---|---|
| `requested` | `policy_check` | orchestrator | always |
| `policy_check` | `queued` | policy gate | permit — **or `not_applicable`** for non-acquisition tasks² |
| `policy_check` | `blocked` | policy gate | deny / unknown / **operation class indeterminate** |
| `blocked` | `awaiting_review` | orchestrator | review required |
| `queued` | `claimed` | worker runtime | lease acquired (CAS) |
| `claimed` | `running` | worker runtime | execution begins |
| `claimed`/`running` | `queued` | orchestrator | **lease expired** → `TaskReclaimed` |
| `running` | `succeeded` | orchestrator | worker reports success + outputs verify |
| `running` | `awaiting_review` | orchestrator | review trigger |
| `running` | `failed` | orchestrator | worker reports failure |
| `failed` | `retry_scheduled` | orchestrator | retryable ∧ attempt < limit |
| `failed` | `dead_lettered` | orchestrator | terminal class ∨ attempts exhausted |
| `retry_scheduled` | `queued` | orchestrator | backoff elapsed |
| `awaiting_review` | `queued` | review gate | approved |
| `awaiting_review` | `suppressed` | review gate | rejected |
| any non-terminal | `cancelled` | operator | explicit, audited |

² Every task passes through `policy_check`, but the gate evaluates only acquisition-class operations.
Non-acquisition tasks (normalize, segment, extract, dedup, review) emit
`PolicyEvaluated(not_applicable)` and proceed. A task whose operation class cannot be determined is
treated as acquisition-class and **blocked** — fail-closed, matching the licensing default.

**Only the orchestrator writes state.** Workers report; reviewers issue commands. Every transition is
an event *before* it is a state. **Any non-terminal state may be `cancelled`** by explicit, audited
operator action; Specification §18.1's diagram shows three representative sources for legibility and
this table is authoritative.

## O. Capability Registry

Approved as a required platform component ([ADR-012 D-16](../adr/ADR-012-automation-platform-architecture.md#d-16--capability-registry--approved)). **Not implemented.**

| Field | Type | R/O | Notes |
|---|---|---|---|
| `capabilityId` | composite | R | `CAP\|<domain>\|<name>` |
| `name` / `description` | string | R | human-readable |
| `version` | semver | R | participates in compatibility checks |
| `owner` | string | R | accountable person or role |
| `acceptedCommands[]` | array<enum> | R | exhaustive; anything else is refused |
| `emittedEvents[]` | array<enum> | R | exhaustive; emitting an undeclared event is a violation |
| `requiredPermissions[]` | array<enum> | R | contexts it may read or write |
| `requiredConnectors[]` | array<connectorId> | R | may invoke no other |
| `requiredSecretReferences[]` | array<secretRef> | R | **names only, never values** |
| `resourceLimits` | object | R | wall clock, memory, disk, max artifact bytes |
| `testSuite` | ref | R | must exist and pass before `approved` |
| `healthStatus` | enum | R | `healthy` \| `degraded` \| `unhealthy` \| `unknown` |
| `lifecycleStatus` | enum | R | `proposed` \| `experimental` \| `approved` \| `production` \| `deprecated` \| `disabled` \| `retired` |
| `enabledState` | bool | R | dispatch requires `true` |
| `compatibility` | object | R | `{commandType: [supportedVersions]}` |
| `deprecationStatus` | object | O | `{since, replacedBy, removeAfter}` |

**Dispatch rule:** the orchestrator may dispatch **only** to a capability that is registered,
`enabledState = true`, in `approved` or `production`, and whose `compatibility` admits the requested
`commandVersion`. Any other case fails and the attempt is recorded.

**Auditability:** every lifecycle transition and enable/disable action is an event.

**Registration confers no scientific authority.** A `production`, enabled capability still cannot
approve a rule, promote a hypothesis, or write scientific evidence — that boundary comes from the
dependency rules and the Constitution, never from registry state.

## M. Licensing policy classification

| Status | Metadata | Transcript | Artifact | Acquire? |
|---|---|---|---|---|
| `PERMITTED_PUBLIC_METADATA` | ✅ | ❌ | ❌ | yes, metadata only |
| `PERMITTED_PUBLIC_TRANSCRIPT` | ✅ | ✅ | ❌ | yes |
| `PERMITTED_PUBLIC_ARTIFACT` | ✅ | ✅ | ✅ | yes |
| `PERMITTED_EXPLICIT_LICENSE` | per licence | per licence | per licence | yes, as recorded |
| `PERMITTED_DOCUMENTED_POLICY` | per policy | per policy | per policy | yes, as recorded |
| `METADATA_ONLY` | ✅ | ❌ | ❌ | metadata only |
| `LINK_ONLY` | locator only | ❌ | ❌ | store locator only |
| `HUMAN_REVIEW_REQUIRED` | already-gathered only¹ | ❌ | ❌ | **no** |
| `AUTHENTICATION_REQUIRED` | ❌ | ❌ | ❌ | **no** |
| `RESTRICTED` | ❌ | ❌ | ❌ | **no** |
| `PROHIBITED` | ❌ | ❌ | ❌ | **no** |
| `UNKNOWN` | ❌ | ❌ | ❌ | **no — identical to PROHIBITED** |

¹ **No new acquisition.** The minimum-metadata allowance exists only in the window *before* a
classification is recorded, to make classification possible. Once a status is recorded, the reviewer
sees the metadata already gathered; no further fetch of any kind occurs. `UNKNOWN` is not a holding
state permitting drip-feed collection — it is `PROHIBITED` with a different reason. See
Specification §20.2.

**Acquisition Authorization Record:** `authorizationId`, `sourceId`, `policyStatus`, `policyVersion`,
`decisionAuthority`, `decidedAt`, `permittedOperations[]`, `sourceTermsSnapshotRef`,
`retentionRestrictions`, `deletionRequirements`, `redistributionRestrictions`,
`modelTrainingRestrictions`, `expiresAt`, `supersedesAuthorizationId`, `auditHistory[]`.

**This catalog makes no legal claim.** It records and enforces decisions supplied by project
governance or legal review.

## N. Review contract

| Field | Notes |
|---|---|
| `reviewId` | uuid |
| `subjectRef` / `reviewType` | what and why |
| `reviewerIdentity` | human or governance role — **never a worker** |
| `decision` | `approved` \| `rejected` \| `deferred` \| `escalated` |
| `reason` | **required** — a bare approval is invalid |
| `decidedAt` / `policyVersion` | when, under which policy |
| `supportingReferences[]` / `auditHistory[]` | evidence and full history |

**No worker may approve its own governed output.** Rejected and suppressed items remain visible and
queryable permanently.
