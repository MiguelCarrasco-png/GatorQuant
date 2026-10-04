<script setup lang="ts">
import { useNav } from '@slidev/client'
const { clicks } = useNav()
// x: settling print 60..140; y: payoff to long side, $ thousands -75..75 (entry 100, cap 30)
const X = (p: number) => 70 + (p - 60) * (560 / 80)
const Y = (v: number) => 190 - v * (150 / 75)
</script>

<template>
  <svg viewBox="0 0 700 400" class="pay">
    <rect :x="X(70)" y="30" :width="X(130) - X(70)" height="320" class="band" :class="{ shown: clicks >= 1 }" />
    <line x1="70" :y1="Y(0)" x2="630" :y2="Y(0)" class="axis" />
    <line :x1="X(100)" y1="30" :x2="X(100)" y2="350" class="axis dashed" />
    <polyline :points="`${X(60)},${Y(-75)} ${X(70)},${Y(-75)} ${X(130)},${Y(75)} ${X(140)},${Y(75)}`" class="line" />
    <circle :cx="X(140)" :cy="Y(75)" r="7" class="pt" :class="{ shown: clicks >= 2 }" />
    <g :class="{ shown: clicks >= 2 }" class="note">
      <line :x1="X(140)" :y1="Y(75) - 12" :x2="X(130)" :y2="Y(75) - 12" class="clip" />
      <text x="76" y="80" class="n1">print 140 is clipped to 130,</text><text x="76" y="98" class="n1">so it pays exactly $75,000</text>
    </g>
    <text x="70" y="378" class="ax">60</text><text :x="X(100)" y="378" text-anchor="middle" class="ax">entry 100</text><text x="630" y="378" text-anchor="end" class="ax">140</text>
    <text x="76" y="52" class="ax">+$75,000 to the winning side</text>
    <text x="624" y="336" text-anchor="end" class="ax">&minus;$75,000 to the losing side</text>
    <text :x="X(100)" y="22" text-anchor="middle" class="ax acc" :class="{ shown: clicks >= 1 }">band: entry ± 30</text>
  </svg>
</template>

<style scoped>
.pay { width: 100%; height: 100%; }
.axis { stroke: #16224a; stroke-width: 1; } .dashed { stroke: #c9d1e0; stroke-dasharray: 3 5; }
.line { fill: none; stroke: #16224a; stroke-width: 3; stroke-linejoin: round; }
.band { fill: #2a3bd1; opacity: 0; transition: opacity .5s; } .band.shown { opacity: .1; }
.pt { fill: #2a3bd1; opacity: 0; transition: opacity .5s; } .pt.shown { opacity: 1; }
.note { opacity: 0; transition: opacity .5s; } .note.shown { opacity: 1; }
.clip { stroke: #2a3bd1; stroke-width: 2; }
.n1 { font: 600 18px 'Archivo Variable', sans-serif; fill: #2a3bd1; }
.ax { font: 400 16px 'Archivo Variable', sans-serif; fill: #5e6a86; }
.acc { fill: #2a3bd1; opacity: 0; transition: opacity .5s; } .acc.shown { opacity: 1; }
</style>
