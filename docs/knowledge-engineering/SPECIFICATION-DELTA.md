# Specification Delta — `alex_g_sr_v1` vs `alex_g_educator_v2_draft`

**MOGO-002.6 Phase 8.** A **knowledge** comparison. Neither specification is declared correct, and nothing here proposes an implementation change.

|  | Production | Draft |
|---|---|---|
| Rules | 13 | 111 |

## Shared domains

| Domain | Production rules | Draft rules |
|---|---|---|
| NO_TRADE_CONDITIONS | 1 | 14 |
| SETUP | 7 | 21 |
| TIMEFRAMES | 2 | 3 |

## Educator-supported additions (draft covers, production does not)

| Domain | Draft rules | Note |
|---|---|---|
| DISCRETIONARY_ELEMENTS | 7 | The educator library covers this domain; the production specification has no rule in it. |
| ENTRY | 27 | The educator library covers this domain; the production specification has no rule in it. |
| INVALIDATION | 9 | The educator library covers this domain; the production specification has no rule in it. |
| LIQUIDITY | 2 | The educator library covers this domain; the production specification has no rule in it. |
| RISK | 13 | The educator library covers this domain; the production specification has no rule in it. |
| SESSION_RESTRICTIONS | 7 | The educator library covers this domain; the production specification has no rule in it. |
| TRADE_MANAGEMENT | 8 | The educator library covers this domain; the production specification has no rule in it. |

## MOGO-authored only (production covers, educator library does not)

| Domain | Production rules | Note |
|---|---|---|
| DIRECTIONAL_BIAS | 1 | The production specification covers this domain; the educator library yields no normalized rule for it. |
| MARKET_STRUCTURE | 2 | The production specification covers this domain; the educator library yields no normalized rule for it. |

## Lineage conflict

**Two unrelated bodies of Alex knowledge**

- **Evidence:** DECISION|MOGO|20260727|004 and traders/alex-g/profile.json state that alex_g_sr_v1's rules come from MOGO's own implementation, NOT this educator's published material. The two specifications share a name and an educator label but not a lineage.
- **Impact:** A domain appearing in both is NOT evidence that the production rule came from the educator. Overlap here is convergence, not derivation.
- **Resolution:** OD-1 already ruled: alex_g_sr_v1 remains production; this draft is source material for a future governed milestone.

## Risk gap

The educator library supplies 13 RISK rules -- all of them SIZING. Stop PLACEMENT rules: 0. The production specification supplies 0 risk rules. Neither body of knowledge states where the stop goes, so the MOGO-002.5 finding GAP-RISK-001 is NOT closed by this draft.

## Trade-management gap

The educator library supplies 8 trade-management rules against 0 in production. This is the one domain where the draft adds materially.

## Exit gap

Neither specification contains a single EXIT rule. Exit behaviour in the shipped engine is entirely MOGO-authored.

