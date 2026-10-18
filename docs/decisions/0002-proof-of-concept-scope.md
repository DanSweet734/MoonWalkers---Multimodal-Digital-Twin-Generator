# 0002 - Proof-of-concept scope: one end-to-end slice, Haas HA5C, machine photos

- **Status:** accepted
- **Date:** 2026-10-16
- **Decided by:** team

## Context
The PoC must show that an AI agent can create a digital twin in some capacity from one input type. Lab
photos arrive later, so inputs are sourced online for now. The machine should be well known, relatively
simple, and have joints and control logic.

## Options considered
1. **Haas HA5C rotary indexer:** one servo-driven spindle (revolute joint); control by stand-alone
   programming with absolute/incremental steps (G90/G91), loops, and a remote cycle start, per the 2006
   operator's manual (https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---ha5c-indexer-operator's-manual---2006.pdf);
   specs on https://haas.co.uk/?p=2253; layout drawing https://www.haas.co.uk/wp-content/uploads/2019/10/HA5C_Dimensions.pdf.
   Haas is one of Dr. Li's six product-data sources. No public CAD found.
2. **Grizzly T33901 drill press:** about five joints, full parts breakdown in the public manual
   (https://cdn0.grizzly.com/manuals/t33901_m.pdf), but minimal control logic.
3. **Prusa CORE One+:** published CAD and open firmware, but more complex.
Build shape: (a) one pipeline end to end with the other three as stubs, or (b) four partial pipelines.

## Decision
HA5C, with the T33901 as backup. Pipeline B (machine photos) runs end to end; Pipelines A, C, D are stubs
returning fixture data in the shared contract.

## Consequences
The PoC proves the orchestrator, knowledge base reuse, and export that every pipeline depends on.
Teammates replace their stub with real code later without touching the rest. Known issue: HA5C max speed
differs by source (410 °/s on the Haas UK page vs. 330 or 320 °/s in the 2006 manual); we use the Haas
UK figure and record the disagreement.

## Update (2026-10-18): the maximum speed, confirmed
The Phase 4 end-to-end run (an agent in a fresh session) chose the manual's 330 °/s for twin v3.
The Haas UK product page was not among its inputs. Daniel confirmed this decision's choice for later
builds: the Haas UK figure, 410 °/s. To make that page available to agents, a copy is saved as
`data/machines/haas-ha5c/inputs/documents/haas-uk_HA5C_product-page_2026-10-18.html` (logged in
`SOURCES.md`). Its specification table still reads "Max Speed 0.001 to 410 °/sec".
`docs/agent-procedure.md` tells agents to follow decision records like this one. Twin v3 keeps the
330 °/s it was built with; the value changes nothing in the simulation until Phase 6 uses it.
