# Deployment effects the baseline omits (brief Section 9)

Question: which real effects does the baseline model leave out (fixed Kepler ellipses, straight-line light time at 8.317 min/AU, 0.10 AU solar exclusion, two sqrt(8) AU relays, 1 s lossless local access), how large are they, and does each one change a pre-funded settlement guarantee or only its timing?

Short answer: none of the five changes **solvency**. Every obligation is locked in full before commit, so a late, lost or reordered message can delay a release but cannot create an unfunded loss. Two of them (clock drift and conjunction blackouts) can change **which** outcome settles when a contract depends on a deadline or on the daily Ceres price. That is a rule-design issue, and the paper should address it explicitly.

"Derived" below means I computed the number from the cited source's formula or constant with circular, coplanar orbits. Those numbers are order-of-magnitude, not ephemeris values.

## 1. Solar conjunction blackout (best sourced, biggest operational effect)

- **Real practice:** NASA stops commanding its Mars fleet for about two weeks around each Mars solar conjunction, which happens roughly every 26 months. The 2015 moratorium ran about June 7-21, while "the sun will be within two degrees of Mars in Earth's sky" ([JPL, 2015](https://www.jpl.nasa.gov/news/mars-missions-to-pause-commanding-in-june-due-to-sun/)). The 2023 moratorium ran Nov 11-25 ([NASA/JPL, 2023](https://www.nasa.gov/solar-system/planets/mars/nasas-mars-fleet-will-still-conduct-science-while-lying-low/)). The cause is coronal plasma corrupting the carrier. DSN 810-005 module 202 models Doppler phase-scintillation error as growing like 1/sin(SEP)^1.225 as the Sun-Earth-probe angle shrinks ([DSN 810-005, 202 Rev. E, eq. 19](https://deepspace.jpl.nasa.gov/dsndocs/810-005/202/202E.pdf)).
- **Baseline comparison (derived):** with circular orbits, the time Mars spends inside 2 deg of the Sun works out to about **14 days**, which matches NASA's two weeks. The baseline's 0.10 AU sphere (about 5.7 deg seen from 1 AU) blocks the direct Earth-Mars line for about **41 days**. For outer planets the blackout is shorter: Earth-Jupiter is about 15 days at 0.10 AU. So the baseline is *conservative* here. The real risk is that the relays are also behind the Sun, or that the corona degrades links outside the sphere (noisy, not cut).
- **Effect on guarantees:** **timing only.** Locks stay funded through the blackout, and releases arrive late. Two exceptions: (a) a Ceres price print that cannot reach a ledger before a contract's deadline, and (b) lock timeouts shorter than the blackout. Both need a written fallback rule, for example "use the last print received" or "extend expiry by the blackout length".

## 2. Relativistic clock-rate drift between planets

- **Number:** clocks on Mars run faster than Earth (geoid) clocks by **477.6 us/day** on average, with a further variation of **226.8 us/day** over a Martian year and about 40 us/day of modulation over seven synodic cycles. The term is mostly gravitational, from Mars sitting higher in the Sun's potential; a smaller part comes from orbital velocity ([Ashby & Patla, *Astron. J.* 171(1), 2025](https://arxiv.org/html/2507.21388v2); [NIST record](https://www.nist.gov/publications/comparative-study-time-mars-lunar-and-terrestrial-clocks)). The paper does not cover the outer planets. The same physics predicts larger offsets there, but I found no sourced number.
- **Scale (derived):** an unsynchronised Mars clock gains about **174 ms per Earth year**, which is about 17% of the baseline's 1 s local-access budget. With routine re-synchronisation (for example daily, alongside the Ceres print) the error stays under 1 ms.
- **Effect on guarantees:** **timing and ordering only, provided every deadline is defined in one reference timescale** (for example TCB, or "receipt time at the home ledger"). If each ledger stamps events in its own proper time, two events that look simultaneous at two settlements can be ordered differently by different ledgers, which leads to disputes over expiry or first commit. Solvency is never at risk because the funds are already locked. The fix is a protocol rule, not more collateral.

## 3. Planetary rotation and ground-station visibility

- **Number:** a Mars solar day is **24.6597 h**, with a sidereal rotation of 24.6229 h ([NASA NSSDC Mars fact sheet](https://nssdc.gsfc.nasa.gov/planetary/factsheet/marsfact.html)). The DSN gets continuous Earth coverage from three complexes "about 120 degrees apart in longitude" ([JPL DSN](https://www.jpl.nasa.gov/missions/dsn/)). By geometry (derived), a single Mars gateway station with no relay orbiter faces away from Earth for about half a sol, roughly **12.3 h**, and longer once an elevation mask is applied.
- **Effect on guarantees:** **timing only.** The baseline's 1 s local access hides a worst case of hours for any settlement that has fewer than about three stations, or a relay orbiter, per gateway. Messages queue, locks stay funded, and settlement latency grows by up to about 12 h. As with conjunction, lock timeouts and price-print deadlines must allow for it.

## 4. Doppler shift on deep-space links

- **Number:** the DSN states that Doppler shift scales with range rate: f_C * v/c one-way and 2 f_C * v/c two-way ([DSN 810-005, 202 Rev. E, eq. 12](https://deepspace.jpl.nasa.gov/dsndocs/810-005/202/202E.pdf)). Derived peak heliocentric range rates are about 14 km/s for Earth-Mars, 27 km/s for Earth-Jupiter, 30 km/s for Earth-Neptune and 36 km/s for Earth-Mercury. That gives v/c of about **0.5-1.2 x 10^-4**, or roughly **0.4-1.0 MHz** one-way at X-band (8.4 GHz).
- **Effect on guarantees:** **none on value; a negligible effect on timing.** Receivers track the offset routinely. The same v/c means the light time changes by up to about 10 s per day, but the baseline's moving Kepler ellipses already capture that.

## 5. Shapiro delay near the Sun

- **Number:** the one-way delay is (2GM/c^3)·ln(4 r1 r2 / b^2), where 2GM_sun/c^3 = 9.85 us ([Shapiro, *PRL* 13, 789 (1964)](https://doi.org/10.1103/PhysRevLett.13.789); confirmed to 2.3e-5 in the Cassini 2002 conjunction test, [Bertotti et al., *Nature* 425, 374 (2003)](https://doi.org/10.1038/nature01997)). Derived for Earth-Mars: **63 us** at the baseline's 0.10 AU edge, **84 us** at the 2 deg NASA limit, and about **124 us one-way, roughly 250 us round-trip,** for a ray grazing the solar limb. For Mercury the published range is 15-240 us between elongation and superior conjunction ([arXiv astro-ph/9510081](https://arxiv.org/pdf/astro-ph/9510081)).
- **Effect on guarantees:** **none.** It is 4-5 orders of magnitude below the 1 s local-access budget and well below the minutes-to-hours light times. It only matters for sub-millisecond timestamp ordering, and Effect 2's single-timescale rule already handles that.

## Summary table

| Effect | Size estimate | Source and assumptions | Effect on guarantees |
|---|---|---|---|
| Solar conjunction blackout | NASA: about 14 d at <2 deg (Mars, every about 26 mo); baseline 0.10 AU: about 41 d Earth-Mars (derived) | JPL 2015/NASA 2023 moratorium releases; DSN 810-005 202 eq. 19; circular coplanar orbits | Timing only; needs a fallback rule for the Ceres print and lock expiry during blackout |
| Relativistic clock drift | Mars +477.6 us/d (±226.8 us/d seasonal), about 174 ms/yr if unsynced | Ashby & Patla 2025 (NIST), Mars reference surface vs Earth geoid | Ordering/timing only, if deadlines use one reference timescale; otherwise expiry disputes |
| Rotation / station visibility | Mars sol 24.66 h; single-station gap about 12.3 h/sol (derived); DSN needs 3 sites 120 deg apart | NSSDC fact sheet; JPL DSN page; no relay orbiter, 0 deg mask | Timing only; settlement latency up to about half a sol |
| Doppler shift | v/c about 0.5-1.2e-4, about 0.4-1.0 MHz at X-band | DSN 810-005 202 eq. 12; derived range rates, circular orbits | None (tracked by receivers) |
| Shapiro delay | 63 us (0.10 AU edge) to about 124 us one-way at limb, Earth-Mars | Shapiro 1964; Cassini/Bertotti 2003; GR formula, gamma = 1 | None (much smaller than the 1 s budget) |
