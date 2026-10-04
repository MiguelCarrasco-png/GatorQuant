<script setup lang="ts">
// "Worst case": a dark shell closes around Ceres at maturity.
// Three SETTLE attempts shatter against it while a clock ring sweeps 72 h; then the shell breaks apart,
// the fourth attempt reaches Callisto and the locked $75,000 is released.
import { ref } from 'vue'
import { useStage, THREE, gsap, C, glow, circle, starfield, arc, comet, sparks, drawIn } from '../lib/stage'

const host = ref<HTMLDivElement>()

useStage(host, (s) => {
  const { scene, camera } = s
  scene.add(starfield(800, 60, C.ink, 0.4))
  const CE = new THREE.Vector3(-1.5, -0.2, 0), CA = new THREE.Vector3(2.1, 0.6, -1.2)

  const body = (p: THREE.Vector3, name: string) => {
    const g = new THREE.Group(), halo = glow(C.ink, 1.1, 0.8)
    g.add(halo, new THREE.Mesh(new THREE.SphereGeometry(0.17, 32, 32), new THREE.MeshBasicMaterial({ color: C.ink })))
    g.position.copy(p); g.scale.setScalar(0); scene.add(g)
    const lab = s.label(name, g, `color:${C.ink2};font-weight:600;font-size:15px;opacity:0`, 0, 38, true)
    return { g, halo, lab }
  }
  const ceres = body(CE, 'Ceres, referee'), cal = body(CA, 'Callisto')

  // Shell: an icosahedron whose faces fly in to close and fly out to break.
  const shellGeo = new THREE.IcosahedronGeometry(1.15, 1).toNonIndexed()
  const base = Float32Array.from(shellGeo.attributes.position.array as Float32Array)
  const faces = base.length / 9
  const fn = new Float32Array(faces * 3), fr = Float32Array.from({ length: faces }, () => 0.6 + Math.random())
  for (let f = 0; f < faces; f++) {
    const v = new THREE.Vector3(base[f * 9] + base[f * 9 + 3] + base[f * 9 + 6], base[f * 9 + 1] + base[f * 9 + 4] + base[f * 9 + 7], base[f * 9 + 2] + base[f * 9 + 5] + base[f * 9 + 8]).normalize()
    fn.set([v.x, v.y, v.z], f * 3)
  }
  const fill = new THREE.MeshBasicMaterial({ color: C.deep, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false })
  const wire = new THREE.MeshBasicMaterial({ color: C.ink2, wireframe: true, transparent: true, opacity: 0 })
  const shell = new THREE.Group(); shell.add(new THREE.Mesh(shellGeo, fill), new THREE.Mesh(shellGeo, wire))
  shell.position.copy(CE); scene.add(shell)
  const sh = { f: 4 }
  const applyShell = () => {
    const a = shellGeo.attributes.position.array as Float32Array
    for (let f = 0; f < faces; f++) for (let v = 0; v < 3; v++) for (let k = 0; k < 3; k++)
      a[f * 9 + v * 3 + k] = base[f * 9 + v * 3 + k] + fn[f * 3 + k] * sh.f * fr[f]
    shellGeo.attributes.position.needsUpdate = true
  }

  const clockRing = circle(1.4, C.saffron, 0.85); clockRing.rotation.x = Math.PI / 2; clockRing.position.copy(CE); scene.add(clockRing)
  const clockTop = new THREE.Object3D(); clockTop.position.set(CE.x, CE.y + 1.4, CE.z); scene.add(clockTop)
  const clockEl = s.label('', clockTop, `color:${C.saffron};font-weight:700;font-size:18px;opacity:0`, 0, -30, true)
  const clock = { h: 0 }

  const cage = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.8, 0.8, 0.8)), new THREE.LineBasicMaterial({ color: C.saffron, transparent: true, opacity: 0 }))
  cage.position.copy(CA); scene.add(cage)
  const cageGlow = glow(C.saffron, 1.6, 0); cageGlow.position.copy(CA); scene.add(cageGlow)
  const cageEl = s.label('$75,000 locked', cage, `color:${C.saffron};font-weight:700;font-size:16px;opacity:0`, 0, -58, true)

  const shock = new THREE.Mesh(new THREE.TorusGeometry(1, 0.015, 8, 128), new THREE.MeshBasicMaterial({ color: C.saffron, transparent: true, opacity: 0 }))
  shock.position.copy(CE); scene.add(shock)

  const pk = comet(scene, C.saffron, 0.55)
  const burst = sparks(scene, C.saffron, 90)
  const pkEl = s.label('', pk.head, `color:${C.saffron};font-weight:600;font-size:14px;opacity:0`, 12, -22)
  const ev = new THREE.Object3D(); ev.position.set(0.3, -2.3, 0); scene.add(ev)
  const evEl = s.label('', ev, `color:${C.ink};font-weight:600;font-size:17px;opacity:0`, 0, 0, true)

  const path = arc(CE, CA, 0.9)
  const hitU = 1.12 / CE.distanceTo(CA)
  const tl = gsap.timeline({ repeat: -1, repeatDelay: 0.6, paused: true })
  const say = (text: string, at: number, end: number) => tl
    .call(() => { evEl.textContent = text }, [], at)
    .fromTo(evEl, { opacity: 0 }, { opacity: 1, duration: 0.35, immediateRender: false }, at)
    .to(evEl, { opacity: 0, duration: 0.35 }, end)
  const attempt = (n: number, at: number, blocked: boolean) => {
    const st = { u: 0 }
    tl.call(() => { pk.start(CE); pkEl.textContent = `SETTLE attempt ${n} of 4` }, [], at)
      .fromTo(pkEl, { opacity: 0 }, { opacity: 1, duration: 0.2, immediateRender: false }, at)
      .fromTo(st, { u: 0 }, { u: blocked ? hitU : 1, duration: blocked ? 0.45 : 1.4, ease: blocked ? 'none' : 'power1.inOut', immediateRender: false, onUpdate: () => { path(st.u, pk.p) } }, at)
    const end = at + (blocked ? 0.45 : 1.4)
    tl.call(() => { burst.burst(pk.p, blocked ? 1.6 : 2.4); pk.hide() }, [], end)
      .to(pkEl, { opacity: 0, duration: 0.3 }, end + (blocked ? 0.6 : 0.2))
    if (blocked) tl.fromTo(wire, { opacity: 1 }, { opacity: 0.5, duration: 0.8, immediateRender: false }, end)
  }

  tl.set(sh, { f: 4 }, 0).set([fill, wire], { opacity: 0 }, 0).set(clock, { h: 0 }, 0).set(cage.scale, { x: 1, y: 1, z: 1 }, 0)
    .call(() => clockRing.geometry.setDrawRange(0, 0), [], 0)
    .fromTo(cage.material, { opacity: 0 }, { opacity: 1, duration: 0.6, immediateRender: false }, 0.3)
    .fromTo(cageGlow.material, { opacity: 0 }, { opacity: 0.35, duration: 0.6, immediateRender: false }, 0.3)
    .fromTo(cageEl, { opacity: 0 }, { opacity: 1, duration: 0.4, immediateRender: false }, 0.4)
    .fromTo(shock.scale, { x: 0.3, y: 0.3, z: 0.3 }, { x: 2.6, y: 2.6, z: 2.6, duration: 1.4, ease: 'expo.out', immediateRender: false }, 0.8)
    .fromTo(shock.material, { opacity: 1 }, { opacity: 0, duration: 1.4, immediateRender: false }, 0.8)
  say('Price printed at maturity. The Ceres winner is paid.', 0.8, 2.2)
  tl.to(sh, { f: 0, duration: 1.4, ease: 'expo.out' }, 2.2)
    .to(fill, { opacity: 0.9, duration: 0.9 }, 2.2).to(wire, { opacity: 0.5, duration: 0.9 }, 2.2)
  say('Ceres is cut off for 72 h', 2.4, 4.4)
  tl.add(drawIn(clockRing, { duration: 7.6, ease: 'none', immediateRender: false }), 2.6)
    .fromTo(clock, { h: 0 }, { h: 72, duration: 7.6, ease: 'none', immediateRender: false }, 2.6)
    .fromTo(clockEl, { opacity: 0 }, { opacity: 1, duration: 0.4, immediateRender: false }, 2.6)
  attempt(1, 3.4, true); attempt(2, 5.6, true); attempt(3, 7.8, true)
  tl.to(clockEl, { opacity: 0, duration: 0.4 }, 10.6)
    .to(sh, { f: 5, duration: 1.3, ease: 'power2.in' }, 10.3).to([fill, wire], { opacity: 0, duration: 1.1 }, 10.4)
    .to(clockRing.material, { opacity: 0, duration: 0.6 }, 10.4).set(clockRing.material, { opacity: 0.85 }, 11.2)
  attempt(4, 10.9, false)
  tl.to(cage.scale, { x: 2, y: 2, z: 2, duration: 0.8, ease: 'power2.out' }, 12.3)
    .to([cage.material, cageGlow.material], { opacity: 0, duration: 0.8 }, 12.3)
    .call(() => { cageEl.textContent = 'Released at +76.1 h' }, [], 12.3)
    .to(cageEl, { opacity: 0, duration: 0.4 }, 14.6).call(() => { cageEl.textContent = '$75,000 locked' }, [], 15)
  say('Paid in full. $0 lost.', 12.4, 14.8)

  s.onTick((t, dt) => {
    applyShell()
    shell.rotation.y = t * 0.25; shell.rotation.x = Math.sin(t * 0.3) * 0.2
    clockEl.textContent = `h ${Math.round(clock.h)} of 72`
    cage.rotation.y = t * 0.6; cage.rotation.x = 0.4
    ceres.halo.material.opacity = 0.7 + Math.sin(t * 2) * 0.1
    pk.tick(); burst.tick(dt)
    camera.position.set(Math.sin(t * 0.1) * 0.8 + 0.3, 1.4, 12.5); camera.lookAt(0.3, -0.2, 0)
  })

  const intro = gsap.timeline({ paused: true })
  ;[ceres, cal].forEach((b, i) => intro
    .fromTo(b.g.scale, { x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1, duration: 0.8, ease: 'back.out(3)' }, i * 0.2)
    .fromTo(b.lab, { opacity: 0 }, { opacity: 0.9, duration: 0.5 }, 0.3 + i * 0.2))
  intro.call(() => { tl.restart() }, [], 0.6)

  s.onEnter(() => {
    tl.pause(0); pk.hide()
    if (s.reduced) { intro.progress(1, true).pause(); tl.progress(0.2, true).pause() }
    else intro.restart()
  })
  return () => tl.kill()
}, { fov: 40 })
</script>

<template>
  <div ref="host" style="position:absolute; inset:0; overflow:hidden" />
</template>
