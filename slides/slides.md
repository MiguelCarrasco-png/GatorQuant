---
theme: default
title: MultiPlanetary Exchange System
aspectRatio: 16/9
canvasWidth: 1280
colorSchema: light
transition: fade
mdc: false
drawings:
  persist: false
layout: none
---

<div class="slide" style="justify-content:flex-end; padding-bottom:120px">
  <h1 class="cover">MultiPlanetary<br>Exchange System</h1>
  <p class="lede">A pre-funded exchange for nine settlements, from Mercury to Neptune. A lost packet can delay a deal but never changes who owns what.</p>
  <div class="foot"><span>Tony Pham and Miguel Carrasco, Gator Quant Hacks 2026</span><span>Design paper and evidence appendix</span></div>
</div>

<!--
Open with the one sentence: lost packets cost time, never money. The whole design follows from it.
-->

---
layout: none
---

<div class="slide night" style="pointer-events:none">
  <LightFront />
  <h2 class="title">The problem</h2>
  <p class="lede" style="max-width:640px">Earth to Neptune is four hours of light each way.</p>
  <p class="lede small" style="max-width:520px">A message can be late, lost, duplicated, or contradicted, and nobody can ask a neighbor. A normal exchange assumes it can. There are nine settlements, no shared clock, and no hub.</p>
  <div class="foot"><span></span><span>2</span></div>
</div>

<!--
The ring is light leaving Earth; the counter on it reaches h 4.2 as it touches Neptune.
Point at Earth and Neptune. The question the brief asks: what do you promise when you cannot confirm?
-->

---
layout: none
---

<div class="slide">
  <h2 class="title">Our answer</h2>
  <p class="lede">Nothing is owed across the lag unless it is locked first.</p>
  <div class="cols three" style="margin-top:52px">
    <div class="item"><h3>Nine Branches</h3><p>One per settlement. Each keeps the only ledger for the assets held there. No hub, no central bank.</p></div>
    <div class="item"><h3>Locks, not timers</h3><p>An asset is reserved for one named deal. Only that deal's recorded outcome ends the lock, never a clock.</p></div>
    <div class="item"><h3>One decider</h3><p>The Branch holding the offer decides once and repeats that answer to every copy of the request.</p></div>
  </div>
  <div style="position:relative; flex:1; min-height:0; margin:4px -84px 0"><BranchLocks /></div>
  <div class="foot"><span>Guarantees G1 to G3 hold whatever the network does</span><span>3</span></div>
</div>

<!--
This is the one idea. Everything after is: how it plays out, and the evidence.
Terms from CONTEXT.md: Branch, Lock, Commit, Deciding Branch.
-->

---
layout: none
clicks: 5
---

<div class="slide">
  <h2 class="title">Share trade</h2>
  <p class="lede small" style="margin-top:14px">Earth buys a share from Neptune. One round trip takes 8.35 hours.</p>
  <div style="flex:1; margin-top:8px; min-height:0"><TradeFlow /></div>
  <div class="foot"><span>If a packet is lost, the lock holder resends. The money stays put.</span><span>4</span></div>
</div>

<!--
Click through: lock, packet crosses, decide, commit crosses back, release.
Key line: the seller can spend at hour 4.2, before the buyer's Branch has even heard back,
because the proceeds are backed by the buyer's lock.
28 backbone packets per trade, 3 count against the quota.
-->

---
layout: none
clicks: 2
---

<div class="slide">
  <h2 class="title">Price contract</h2>
  <p class="lede small" style="margin-top:14px">A capped Ceres Iron future over 288 hours. Both sides lock their worst case before the position opens.</p>
  <div style="display:grid; grid-template-columns: 1.15fr 1fr; gap:56px; flex:1; margin-top:12px; min-height:0">
    <PayoffChart />
    <div style="align-self:center">
      <div class="item" style="margin-bottom:30px"><h3>Paid in full either way</h3><p>The winner is paid from locked assets. No margin call, no default.</p></div>
      <div class="item" style="margin-bottom:30px"><div class="big">30%</div><p>of all cash locked: $150,000 for 288 hours. That is the price of the guarantee.</p></div>
      <div class="item"><div class="big">0.69 h</div><p>after maturity, the remote winner can spend (hour 288.69).</p></div>
    </div>
  </div>
  <div class="foot"><span>Settled by the Branch where the price is published</span><span>5</span></div>
</div>

<!--
Clip = force the settling print into entry ± cap. That is why maximum loss is known up front.
The binding case on the chart is the one in the paper: print 140, clipped to 130, pays exactly the whole $75,000 lock.
-->

---
layout: none
---

<div class="slide">
  <h2 class="title">Guarantees</h2>
  <p class="lede small" style="margin-top:14px">G1 to G3 survive any network behavior. G4 depends on the orbit model, and we say so.</p>
  <table class="tbl">
    <thead><tr><th style="width:80px"></th><th style="width:500px">Guarantee</th><th>Rests on</th></tr></thead>
    <tbody>
      <tr><td>G1</td><td>Funding is conserved; no asset serves two uses</td><td>Rules alone. Checked after every ledger step.</td></tr>
      <tr><td>G2</td><td>A cross-planet deal is all or nothing</td><td>Rules alone. One recorded outcome per deal ID.</td></tr>
      <tr><td>G3</td><td>Every price contract pays in full, both directions</td><td>Rules alone. Max loss locked before opening.</td></tr>
      <tr><td>G4</td><td>Every lock ends, if the two Branches can eventually exchange a packet</td><td>Rules plus the orbit model.</td></tr>
    </tbody>
  </table>
  <div class="foot"><span></span><span>6</span></div>
</div>

<!--
Be explicit about the difference between "rules" and "model". The honest conditional on G4 is a strength.
-->

---
layout: none
---

<div class="slide">
  <h2 class="title">Evidence</h2>
  <p class="lede small" style="margin-top:14px">We tried to break it. It held.</p>
  <div class="stat-row">
    <div class="stat"><div class="n">75</div><div class="l">conservation and single-use checks over 16 simulated runs. None failed.</div></div>
    <div class="stat"><div class="n">200<small>yr</small></div><div class="l">orbit scan certified to 1 ms. No settlement is ever cut off; every pair is at most three links apart.</div></div>
    <div class="stat"><div class="n">100<small>%</small></div><div class="l">route availability in every 24 h window, by pinning routes with foresight.</div></div>
  </div>
  <p class="lede small" style="margin-top:48px">Random packet loss only delays. Earth to Neptune completes at its no-loss time 30% of the time and within 24 h of it 79% of the time. The lock stays in place throughout.</p>
  <div class="foot"><span>Appendix S1 to S3, E1 to E5</span><span>7</span></div>
</div>

<!--
Do not oversell: random loss means no unconditional deadline exists. We said that in the paper.
-->

---
layout: none
---

<div class="slide night">
  <div style="position:absolute; top:0; right:0; bottom:0; width:640px"><RefereeBlackout /></div>
  <h2 class="title">Worst case</h2>
  <p class="lede" style="margin-top:14px; max-width:520px">The referee Branch is cut off for 72 hours at maturity.</p>
  <div class="stat-stack">
    <div class="stat"><div class="n">76.1<small>h</small></div><div class="l">late for the payment. Callisto's $75,000 stays locked that much longer.</div></div>
    <div class="stat"><div class="n">$0</div><div class="l">change in any balance. The Ceres winner is paid at the print regardless.</div></div>
    <div class="stat"><div class="n">4</div><div class="l">endpoint attempts for SETTLE to land, kept alive by a recovery reserve new trade cannot use.</div></div>
  </div>
  <p class="lede small" style="margin-top:30px; max-width:500px">The party that was cut off pays for the outage in time. Nobody loses value.</p>
  <div class="foot"><span>Appendix S2</span><span>8</span></div>
</div>

<!--
Ranked #1 of ten risks. Others: a route closing mid-contract (E5), pinning the fastest route (E4).
-->

---
layout: none
---

<div class="slide">
  <h2 class="title">Limits</h2>
  <p class="lede small" style="margin-top:14px">What the design costs and where it stops.</p>
  <div class="cols two" style="margin-top:40px">
    <div class="item"><h3>Capital sits locked</h3><p>A far client cannot recall money early during an outage. No leverage: you open only what your free balance covers.</p></div>
    <div class="item"><h3>8.2 to 12.4 h for Neptune</h3><p>One light round trip per deal. Far clients see prices later than Ceres clients.</p></div>
    <div class="item"><h3>Bounded loss only</h3><p>Futures held to maturity. No new positions in the final 24 h.</p></div>
    <div class="item"><h3>Effects we left out</h3><p>Solar conjunction and similar real-world effects can delay a deal. None can unfund one.</p></div>
  </div>
  <div class="foot"><span>Every rule is marked implemented or extension in the paper</span><span>9</span></div>
</div>

<!--
Check the deployment table in the paper (section 5) before adding specifics; its sizes are derived estimates, not ephemeris values.
-->

---
layout: none
---

<div class="slide night">
  <h2 class="title">Summary</h2>
  <ol class="rules">
    <li>Lock first.<span>No deal moves without assets reserved for it.</span></li>
    <li>Decide once.<span>One Branch records the outcome and repeats it.</span></li>
    <li>Resend until it lands.<span>A lost packet costs time, never money.</span></li>
  </ol>
  <div class="foot"><span>Tony Pham and Miguel Carrasco</span><span>Questions</span></div>
</div>

<!--
Hand off to Q&A. Appendix pages are the backup for any number challenged.
-->
