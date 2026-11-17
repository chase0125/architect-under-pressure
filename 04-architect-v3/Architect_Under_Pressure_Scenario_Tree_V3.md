# Architect Under Pressure - Scenario Tree & Logic Specification (V3)

**Implementation rule:** Chase may use Gemini or another coding assistant to implement/refactor the game. This document is the source of truth for cloud logic, wording, score effects, flags, consequences, and endings. Do not let the coding assistant invent or rewrite those elements unless Duke approves a change.

## Game context
A fictional commerce platform is running a midnight product launch on Google Cloud. The customer-facing API runs on Cloud Run, transactional data is in Cloud SQL for PostgreSQL, Pub/Sub handles order-confirmation work, Cloud Armor is available at the edge, and Cloud Monitoring / Query Insights are available for diagnosis. A release went out at 1:50 AM. Marketing can pause or resume the paid launch campaign.

## Engine rules
- Start all five player scores at 50: Reliability, Security, Cost Efficiency, Response Speed, Judgment.
- Clamp every score to 0-100 after each choice.
- Gameplay loop: scene start state -> exact prompt -> player choice -> apply score deltas/flags -> exact consequence -> post-choice state/metrics -> Continue -> next scene.
- Never skip the consequence step. Disable the choice buttons immediately after one is selected.
- Every selected choice must be stored in a decision log.
- Endings are determined by state flags first and scores second. Do not infer the ending from scores alone.
- No runtime Gemini is required for this version. Gemini may be used to write the code, but the game logic remains deterministic.

## Flow
Scene 1 -> Scene 2 -> Scene 3 -> Scene 4 -> Scene 5 -> Aftermath Report. Choices change scores, flags, consequences, and final classification; they do not need separate scene files.

## Scene 1 - The bottleneck (2:17 AM)
**Start state:** Status: CRITICAL | Metrics: Checkout p95: 4.8s | Error rate: 9% | Cloud SQL CPU: 96% | Cloud Run CPU: 41%

**Exact prompt**
```text
Pager alert: checkout latency is climbing fast during a scheduled product launch. Cloud SQL is saturated, but Cloud Run still has headroom.

CEO: "Traffic is exploding. Keep checkout online."

What do you do first?
```

### 1A - Increase the Cloud Run maximum instance limit
- **Score effects:** REL -5 | SEC +0 | CST-EFF -10 | SPD +5 | JUD -10
- **Flags:** Set: scaledWrongLayer
- **Exact consequence:** Cloud Run adds capacity, but the database becomes even more constrained as more application instances compete for database connections. Checkout slows further.
- **Post-state:** CRITICAL | Checkout p95: 5.6s | Error rate: 13% | Cloud SQL CPU: 99% | Cloud Run CPU: 36%
- **Aftermath decision-log line:** You scaled the application layer even though the database was the limiting resource.

### 1B - Scale Cloud SQL up one tier
- **Score effects:** REL +10 | SEC +0 | CST-EFF -15 | SPD +10 | JUD -5
- **Flags:** Set: dbScaled
- **Exact consequence:** Database headroom improves and checkout errors fall, but the expensive query is still running. You bought time without removing the cause.
- **Post-state:** DEGRADED | Checkout p95: 2.1s | Error rate: 4% | Cloud SQL CPU: 76% | Cloud Run CPU: 43%
- **Aftermath decision-log line:** You bought immediate database headroom, improving availability at additional cost without yet fixing root cause.

### 1C - Inspect Cloud Monitoring and Query Insights first
- **Score effects:** REL +5 | SEC +0 | CST-EFF +5 | SPD -5 | JUD +15
- **Flags:** Set: rootCauseFoundEarly
- **Exact consequence:** Within two minutes, Query Insights shows one checkout query consuming most database time. The regression began immediately after the 1:50 AM release.
- **Post-state:** DEGRADED | Top query: 63% of DB time | Release age: 27 min | Error rate: 9%
- **Aftermath decision-log line:** You diagnosed the bottleneck before adding infrastructure.

## Scene 2 - The query regression (2:24 AM)
**Start state:** Status: INHERIT | Metrics: INHERIT

**Exact prompt (default)**
```text
A few minutes later, the database evidence is clear: the 1:50 AM release introduced a checkout query that scans the orders table because a supporting index was omitted. The previous release is still available, and the schema is backward compatible.

Marketing has paused the paid campaign while checkout is degraded.

What do you do?
```
**If `rootCauseFoundEarly=true`, use instead:**
```text
Your investigation confirms the cause: the 1:50 AM release introduced a checkout query that scans the orders table because a supporting index was omitted. The previous release is still available, and the schema is backward compatible.

Marketing has paused the paid campaign while checkout is degraded.

What do you do?
```

### 2A - Roll back the 1:50 AM release
- **Score effects:** REL +15 | SEC +0 | CST-EFF +5 | SPD +10 | JUD +15
- **Flags:** Set: queryFixed, releaseRolledBack; Clear: workaroundOnly
- **Exact consequence:** Rollback completes in about three minutes. The regressed query disappears and checkout returns close to baseline. The new feature is temporarily unavailable, but production stabilizes.
- **Post-state:** STABLE | Checkout p95: 420ms | Error rate: 0.8% | Cloud SQL CPU: 44%
- **Aftermath decision-log line:** You used a reversible rollback to restore checkout quickly and removed the query regression.

### 2B - Create the missing index concurrently and keep the release live
- **Score effects:** REL +10 | SEC +0 | CST-EFF +0 | SPD -5 | JUD +10
- **Flags:** Set: queryFixed, indexHotfix; Clear: workaroundOnly
- **Exact consequence:** The concurrent index avoids blocking normal table access, but it consumes database capacity while building. After about eight minutes, the query drops from seconds to milliseconds and checkout stabilizes.
- **Post-state:** STABLE | Checkout p95: 650ms | Error rate: 1.2% | Cloud SQL CPU: 58% | Index: complete
- **Aftermath decision-log line:** You fixed the query in place while accepting a longer period of elevated database load.

### 2C - Scale Cloud SQL again and leave the release unchanged
- **Score effects:** REL +10 | SEC +0 | CST-EFF -20 | SPD +10 | JUD -10
- **Flags:** Set: workaroundOnly; Clear: queryFixed
- **Exact consequence:** Checkout recovers enough to continue, but the regressed query remains. The larger database is masking the problem rather than fixing it.
- **Post-state:** DEGRADED | Checkout p95: 1.4s | Error rate: 2.6% | Cloud SQL CPU: 72% | DB size: +2 tiers
- **Aftermath decision-log line:** You restored headroom by scaling around the regression, leaving the root cause in production.

## Scene 3 - The login attack (2:38 AM)
**Start state:** Status: CRITICAL | Metrics: Failed logins: 7,800/min | Suspicious successful logins: 23

**Exact prompt**
```text
While checkout is recovering, authentication monitoring flags 7,800 failed logins per minute against many customer accounts. Most attempts come from a relatively small set of client networks, but legitimate login traffic is also elevated. A few suspicious sessions have already succeeded.

What do you do?
```

### 3A - Rate-limit /login at the edge and force resets for suspicious accounts
- **Score effects:** REL +5 | SEC +20 | CST-EFF +0 | SPD +5 | JUD +15
- **Flags:** Set: attackContained; Clear: attackActive
- **Exact consequence:** The failed-login rate falls sharply. Legitimate users see minor friction, suspicious sessions are revoked, and affected accounts are forced through password reset.
- **Post-state:** STABLE | Failed logins: 310/min | Suspicious sessions: revoked | Threat: CONTAINED
- **Aftermath decision-log line:** You used targeted abuse controls and account remediation instead of treating malicious traffic as a pure capacity problem.

### 3B - Block the suspicious IP ranges immediately
- **Score effects:** REL +0 | SEC +10 | CST-EFF +0 | SPD +10 | JUD -5
- **Flags:** Set: broadBlock, attackPartiallyContained; Clear: attackActive
- **Exact consequence:** Attack volume drops quickly, but some legitimate users behind shared networks are blocked. New attacker IPs begin appearing, so the control is only partially effective.
- **Post-state:** DEGRADED | Failed logins: 1,900/min | Legitimate blocks: elevated | Threat: PARTIAL
- **Aftermath decision-log line:** You reduced attack volume quickly, but used a broad control that also blocked legitimate customers.

### 3C - Scale authentication capacity and continue monitoring
- **Score effects:** REL +5 | SEC -25 | CST-EFF -15 | SPD +10 | JUD -15
- **Flags:** Set: attackActive, accountsCompromised; Clear: attackContained
- **Exact consequence:** The login service remains responsive, but the credential attack continues. More customer accounts are taken over because extra capacity addressed availability, not abuse.
- **Post-state:** CRITICAL | Login p95: 280ms | Compromised accounts: 61 | Threat: ACTIVE
- **Aftermath decision-log line:** You kept authentication available but failed to contain the credential attack, allowing additional account compromise.

## Scene 4 - The recovery backlog (2:47 AM)
**Start state:** If attackActive=true: Status CRITICAL and include "Threat: ACTIVE" with the backlog metrics. Otherwise: Status DEGRADED. Base metrics: Pub/Sub backlog: 18,400 messages | Oldest message: 21 min | Cloud SQL CPU: 84%

**Exact prompt**
```text
During the earlier slowdown, order-confirmation workers fell behind. Pub/Sub now has 18,400 undelivered messages. As the workers scale to catch up, database CPU starts climbing again.

Customer-facing checkout is currently usable.

How do you recover the backlog?
```

### 4A - Let the workers scale freely and drain the backlog as fast as possible
- **Score effects:** REL -10 | SEC +0 | CST-EFF -10 | SPD +15 | JUD -10
- **Flags:** Set: recoveryOverload
- **Exact consequence:** The backlog drops quickly, but the workers hammer the same database you just stabilized. Customer checkout latency climbs above two seconds again.
- **Post-state:** DEGRADED | Backlog: 3,200 | Cloud SQL CPU: 92% | Checkout p95: 2.3s
- **Aftermath decision-log line:** You optimized backlog speed at the expense of renewed pressure on the customer-facing database.

### 4B - Cap worker concurrency and drain the backlog gradually
- **Score effects:** REL +15 | SEC +0 | CST-EFF +5 | SPD -5 | JUD +15
- **Flags:** Set: backlogControlled
- **Exact consequence:** The queue drains more slowly, but database CPU stays below 60% and customer-facing checkout remains healthy.
- **Post-state:** STABLE | Backlog: 9,600 and falling | Cloud SQL CPU: 57% | Checkout p95: 480ms
- **Aftermath decision-log line:** You protected the primary workload by throttling recovery work and accepting a slower backlog drain.

### 4C - Purge the backlog and reconcile affected orders from the database later
- **Score effects:** REL -20 | SEC +0 | CST-EFF -5 | SPD +15 | JUD -25
- **Flags:** Set: recoveryDataGap
- **Exact consequence:** The queue clears immediately, but 1,126 confirmation and downstream fulfillment events are no longer processed automatically. A manual reconciliation effort is now required.
- **Post-state:** DEGRADED | Backlog: 0 | Unreconciled orders: 1,126 | Manual recovery: REQUIRED
- **Aftermath decision-log line:** You cleared the queue by discarding pending work, creating a customer-impacting reconciliation problem.

## Scene 5 - Return to launch traffic (3:05 AM)
**Start state:** If attackActive=true: CRITICAL. Else if workaroundOnly, recoveryOverload, recoveryDataGap, or broadBlock=true: DEGRADED. Else: STABLE. Base metrics: Paid campaign: PAUSED | Customer traffic: baseline | Incident: RECOVERING

**Exact prompt**
```text
The business wants the launch back. The paid campaign has been paused since checkout degraded.

CEO: "Can we restart the campaign at full volume now? Every minute paused costs us sales."

What do you recommend?
```

### 5A - Restore full campaign traffic immediately
- **Score effects:** REL -10 | SEC +0 | CST-EFF +0 | SPD +15 | JUD -10
- **Flags:** Set: fullTrafficRestored, unguardedRamp
- **Conditional rule:** If any of workaroundOnly, attackActive, recoveryOverload, or recoveryDataGap is true, also set incidentReopened=true. Otherwise do not set incidentReopened.
- **Safe consequence:** Full traffic returns and the platform remains available, but you skipped a validation window and accepted unnecessary operational risk.
- **Safe post-state:** DEGRADED | Campaign: 100% | Checkout p95: 820ms | Incident: MONITORING
- **Risky consequence:** Full campaign traffic hits an environment with unresolved risk. Customer-facing errors climb again and the incident is reopened.
- **Risky post-state:** CRITICAL | Campaign: 100% | Error rate: 18% | Incident: REOPENED
- **Aftermath decision-log line:** You restored full launch traffic without a staged validation period.

### 5B - Keep the campaign paused until the system is stable for 30 minutes
- **Score effects:** REL +15 | SEC +0 | CST-EFF +0 | SPD -15 | JUD +10
- **Flags:** Set: conservativeRecovery, stableEnd
- **Exact consequence:** You hold traffic at baseline and keep the incident open for observation. The platform remains stable, but the business gives up additional launch revenue while you validate recovery.
- **Post-state:** STABLE | Campaign: PAUSED | Checkout p95: 430ms | Observation window: 30 min
- **Aftermath decision-log line:** You favored a longer observation window over launch speed.

### 5C - Resume at 10%, watch SLOs for 10 minutes, then ramp if healthy
- **Score effects:** REL +10 | SEC +0 | CST-EFF +0 | SPD +5 | JUD +20
- **Flags:** Set: guardedRamp, stableEnd
- **Conditional rule:** If any of workaroundOnly, attackActive, recoveryOverload, or recoveryDataGap is true, show the risk-detected consequence and keep campaign at 10%/paused after threshold breach. Otherwise show the healthy consequence and ramp to 100%. Do not set incidentReopened.
- **Safe consequence:** The 10% canary stays within latency and error thresholds. Traffic ramps gradually to 100% and the launch resumes without reopening the incident.
- **Safe post-state:** STABLE | Campaign: 100% | Checkout p95: 470ms | Error rate: 0.9% | SLOs: HEALTHY
- **Risky consequence:** The 10% canary exposes the remaining weakness before full traffic returns. Your rollback threshold trips, the campaign is paused again, and production stays available while the open issue is addressed.
- **Risky post-state:** STABLE | Campaign: PAUSED | Production: STABLE | Remaining risk: DETECTED
- **Aftermath decision-log line:** You used a guarded traffic ramp with explicit health thresholds rather than making an all-or-nothing launch decision.

## Ending logic - exact priority order
1. **INCIDENT REOPENED / UNRESOLVED** if `incidentReopened=true`.
   - Exact summary: "The final recovery decision returned load to an environment with unresolved risk, and the incident became active again. Production is not in a clean recovery state."
2. **SERVICE RESTORED, CUSTOMER IMPACT REMAINS** if `accountsCompromised=true` or `recoveryDataGap=true` (and incidentReopened is false).
   - Exact summary: "The core service is available, but the incident caused customer-impacting security or order-processing problems that still require remediation. Availability alone does not make this a clean recovery."
3. **STRONG RECOVERY** if none of `workaroundOnly`, `broadBlock`, `recoveryOverload`, or `unguardedRamp` is true AND Reliability >= 65 AND Security >= 60 AND Cost Efficiency >= 35 AND Judgment >= 65.
   - Exact summary: "You diagnosed and mitigated the incident without leaving a major operational shortcut behind. The platform is stable, customer-impacting risks are contained, and the return to traffic was controlled."
4. **RECOVERY WITH TRADEOFFS** for every remaining path.
   - Exact summary: "Production is available, but your recovery path left meaningful operational tradeoffs such as unnecessary spend, broad customer blocking, an unfixed regression, renewed database pressure, or an unguarded return to traffic."

### Aftermath report content
Show: ending title, exact ending summary, final five scores, then **Decision Log** containing the five selected choices' `debrief` lines in chronological order. Do not generate a generic personality label such as "The Big Spender."

## Required acceptance tests
- `1C -> 2A -> 3A -> 4B -> 5C` => **STRONG RECOVERY**
- `1B -> 2B -> 3A -> 4B -> 5C` => **STRONG RECOVERY**
- `1C -> 2A -> 3B -> 4B -> 5C` => **RECOVERY WITH TRADEOFFS**
- `1C -> 2C -> 3A -> 4B -> 5C` => **RECOVERY WITH TRADEOFFS**
- `1C -> 2A -> 3C -> 4B -> 5B` => **SERVICE RESTORED, CUSTOMER IMPACT REMAINS**
- `1C -> 2A -> 3A -> 4C -> 5B` => **SERVICE RESTORED, CUSTOMER IMPACT REMAINS**
- `1A -> 2C -> 3C -> 4C -> 5A` => **INCIDENT REOPENED / UNRESOLVED**

Implementation must also verify that every `incidentReopened=true` path ends as INCIDENT REOPENED / UNRESOLVED, and that any non-reopened path with `accountsCompromised=true` or `recoveryDataGap=true` cannot receive STRONG RECOVERY.

## Technical grounding
- Cloud SQL Query Insights is intended to diagnose query performance problems.
- Cloud Run maximum-instance settings can be used to constrain scaling and protect backing services such as databases.
- Cloud Armor supports per-client rate limiting / rate-based controls used to mitigate abusive request floods including credential-stuffing-style traffic.
- Pub/Sub exposes backlog health through undelivered/unacknowledged-message metrics and oldest-message age.
- Cloud Run supports gradual traffic rollouts and traffic splitting, which is the model behind the guarded-ramp decision.