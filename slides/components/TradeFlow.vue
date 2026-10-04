<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useNav } from '@slidev/client'
import gsap from 'gsap'

const { clicks } = useNav()
const L = 430, R = 770
const events = [
  { y: 100, side: 'L', h: 'h 0.0', t: 'Lock the buyer’s $25,000', s: 'Reserved for this deal. No timer frees it.' },
  { y: 215, side: 'R', h: 'h 4.2', t: 'Decide once: commit', s: 'Seller can spend now, backed by the lock.' },
  { y: 330, side: 'L', h: 'h 8.4', t: 'Release on commit', s: 'Share delivered. Trade complete.' },
]
const p1 = ref<SVGCircleElement>(), p2 = ref<SVGCircleElement>()
const fly = (el: SVGCircleElement | undefined, x0: number, y0: number, x1: number, y1: number) => {
  if (!el) return
  gsap.fromTo(el, { attr: { cx: x0, cy: y0 }, opacity: 1 },
    { attr: { cx: x1, cy: y1 }, duration: 1.1, ease: 'power2.inOut', onComplete: () => { gsap.to(el, { opacity: 0, duration: .2 }) } })
}
watch(clicks, (c, o) => {
  if (c === 2 && o < 2) fly(p1.value, L, 100, R, 215)
  if (c === 4 && o < 4) fly(p2.value, R, 215, L, 330)
})
onMounted(() => { gsap.set([p1.value, p2.value], { opacity: 0 }) })
const on = (n: number) => clicks.value >= n
</script>

<template>
  <svg viewBox="0 0 1100 420" class="flow">
    <text :x="L" y="28" class="who">Earth, initiator Branch</text>
    <text :x="R" y="28" class="who">Triton, deciding Branch</text>
    <line :x1="L" y1="44" :x2="L" y2="400" class="life" />
    <line :x1="R" y1="44" :x2="R" y2="400" class="life" />
    <line :x1="L" y1="100" :x2="R" y2="215" class="path" :class="{ shown: on(2) }" />
    <line :x1="R" y1="215" :x2="L" y2="330" class="path" :class="{ shown: on(4) }" />
    <g v-for="(e, i) in events" :key="i" class="ev" :class="{ shown: on(i === 0 ? 1 : i === 1 ? 3 : 5) }">
      <circle :cx="e.side === 'L' ? L : R" :cy="e.y" r="7" class="node" />
      <g :transform="`translate(${e.side === 'L' ? L - 28 : R + 28}, ${e.y})`" :text-anchor="e.side === 'L' ? 'end' : 'start'">
        <text y="-18" class="hr">{{ e.h }}</text>
        <text y="6" class="tt">{{ e.t }}</text>
        <text y="30" class="ss">{{ e.s }}</text>
      </g>
    </g>
    <circle ref="p1" r="9" class="pk" /><circle ref="p2" r="9" class="pk" />
    <text x="600" y="140" class="lbl" :class="{ shown: on(2) }" text-anchor="middle" transform="rotate(18.7 600 140)">Lock request, about 4 h of light</text>
    <text x="600" y="290" class="lbl" :class="{ shown: on(4) }" text-anchor="middle" transform="rotate(-18.7 600 290)">Commit, about 4 h back</text>
  </svg>
</template>

<style scoped>
.flow { width: 100%; height: 100%; }
.who { font: 700 17px 'Archivo Variable', sans-serif; fill: #16224a; text-anchor: middle; }
.life { stroke: #c9d1e0; stroke-width: 1; stroke-dasharray: 3 5; }
.path { stroke: #2a3bd1; stroke-width: 1.5; opacity: 0; transition: opacity .5s .9s; }
.path.shown { opacity: .5; }
.ev { opacity: 0; transition: opacity .5s; }
.ev.shown { opacity: 1; }
.ev .node { fill: #16224a; }
.hr { font: 600 15px 'Archivo Variable', sans-serif; fill: #2a3bd1; }
.tt { font-family: 'Archivo Variable', sans-serif; font-weight: 700; font-size: 23px; font-stretch: 112%; fill: #16224a; }
.ss { font: 400 16px 'Archivo Variable', sans-serif; fill: #5e6a86; }
.pk { fill: #2a3bd1; }
.lbl { font: 400 14px 'Archivo Variable', sans-serif; fill: #5e6a86; opacity: 0; transition: opacity .5s .9s; }
.lbl.shown { opacity: 1; }
</style>
