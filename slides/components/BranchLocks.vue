<script setup lang="ts">
// "Our answer": nine Branches, each with its own ring of assets.
// Earth locks six coins in a cage, the request crosses to Neptune, Neptune decides once and gives the same
// answer to a resent copy, and the commit releases the coins to Neptune.
import { ref } from 'vue'
import { useStage, THREE, gsap, C, BODIES, glow, arc } from '../lib/stage'

const host = ref<HTMLDivElement>()
const EARTH = 2, NEPTUNE = 8, COINS = 10

useStage(host, (s) => {
  const { scene, camera } = s
  scene.add(new THREE.HemisphereLight('#ffffff', '#b8c2d8', 2.2))
  const sunLight = new THREE.DirectionalLight('#ffffff', 1.6); sunLight.position.set(3, 6, 8); scene.add(sunLight)

  const coinGeo = new THREE.CylinderGeometry(0.075, 0.075, 0.03, 24)
  const coinMat = new THREE.MeshStandardMaterial({ color: C.ultra, roughness: 0.35, metalness: 0.3 })
  type Coin = { m: THREE.Mesh; owner: number; a: number; free: boolean }
  const coins: Coin[] = []
  const nodes = BODIES.map((b, i) => {
    const g = new THREE.Group()
    g.position.set(-10 + i * 2.5, 0, -Math.pow((i - 4) / 4, 2) * 1.6)
    const ball = new THREE.Mesh(new THREE.SphereGeometry(0.26, 32, 32), new THREE.MeshStandardMaterial({ color: C.navy, roughness: 0.45, metalness: 0.1 }))
    const ring = new THREE.Mesh(new THREE.TorusGeometry(0.52, 0.01, 8, 128), new THREE.MeshBasicMaterial({ color: C.ultra, transparent: true, opacity: 0.45 }))
    ring.rotation.x = Math.PI / 2 - 0.32
    g.add(ball, ring); g.scale.setScalar(0); scene.add(g)
    for (let k = 0; k < COINS; k++) {
      const m = new THREE.Mesh(coinGeo, coinMat); scene.add(m)
      coins.push({ m, owner: i, a: (k / COINS) * Math.PI * 2, free: false })
    }
    const lab = s.label(b.name, g, `color:${C.navy};font-weight:600;font-size:15px;opacity:0`, 0, 30, true)
    return { g, ring, lab }
  })
  const E = nodes[EARTH].g.position, N = nodes[NEPTUNE].g.position

  const cagePos = new THREE.Vector3(E.x, 1.15, E.z)
  const cage = new THREE.Group()
  cage.add(new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(0.8, 0.8, 0.8)), new THREE.LineBasicMaterial({ color: C.ultra, transparent: true })),
    new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.8, 0.8), new THREE.MeshBasicMaterial({ color: C.ultra, transparent: true, opacity: 0.07, depthWrite: false })))
  cage.position.copy(cagePos); cage.scale.setScalar(0); scene.add(cage)
  const cageMats = cage.children.map(c => (c as THREE.Mesh).material as THREE.Material)

  const packet = () => {
    const g = new THREE.Group()
    g.add(new THREE.Mesh(new THREE.SphereGeometry(0.15, 24, 24), new THREE.MeshBasicMaterial({ color: C.ultra })), glow(C.ultra, 1.1, 0.4, false))
    g.visible = false; scene.add(g); return g
  }
  const pk1 = packet(), pk2 = packet()
  const shock = () => {
    const m = new THREE.Mesh(new THREE.TorusGeometry(1, 0.012, 8, 128), new THREE.MeshBasicMaterial({ color: C.ultra, transparent: true, opacity: 0 }))
    m.position.copy(N); m.rotation.x = Math.PI / 2 - 0.32; scene.add(m); return m
  }
  const sh1 = shock(), sh2 = shock()
  const ev = new THREE.Object3D(); scene.add(ev)
  const evEl = s.label('', ev, `color:${C.ultra};font-weight:700;font-size:17px;opacity:0`, 0, -40, true)

  const locked = coins.filter(c => c.owner === EARTH).slice(0, 6)
  const slot = (k: number) => new THREE.Vector3(cagePos.x + ((k % 3) - 1) * 0.22, cagePos.y + (Math.floor(k / 3) - 0.5) * 0.24, cagePos.z)
  const orbitPos = (c: Coin, out: THREE.Vector3) => nodes[c.owner].ring.localToWorld(out.set(Math.cos(c.a) * 0.52, Math.sin(c.a) * 0.52, 0))

  // Move a coin from wherever it is now to `to`, along a small arc.
  const flyCoin = (tl: gsap.core.Timeline, c: Coin, to: () => THREE.Vector3, lift: number, dur: number, at: number) => {
    const st = { u: 0 }; let path: ReturnType<typeof arc> | null = null
    tl.fromTo(st, { u: 0 }, {
      u: 1, duration: dur, ease: 'power2.inOut', immediateRender: false,
      onStart: () => { c.free = true; path = arc(c.m.position, to(), lift) },
      onUpdate: () => { if (path && st.u > 0) path(st.u, c.m.position) },
      onComplete: () => { path = null },
    }, at)
  }
  const fly = (tl: gsap.core.Timeline, obj: THREE.Object3D, a: THREE.Vector3, b: THREE.Vector3, lift: number, dur: number, at: number) => {
    const path = arc(a, b, lift), st = { u: 0 }
    tl.set(obj, { visible: true }, at)
      .fromTo(st, { u: 0 }, { u: 1, duration: dur, ease: 'power1.inOut', immediateRender: false, onUpdate: () => { path(st.u, obj.position) } }, at)
      .set(obj, { visible: false }, at + dur)
  }
  const say = (tl: gsap.core.Timeline, text: string, where: THREE.Vector3, at: number, hold = 1.8) => tl
    .call(() => { evEl.textContent = text; ev.position.copy(where) }, [], at)
    .fromTo(evEl, { opacity: 0 }, { opacity: 1, duration: 0.3, immediateRender: false }, at)
    .to(evEl, { opacity: 0, duration: 0.3 }, at + hold)
  const pulse = (tl: gsap.core.Timeline, m: THREE.Mesh, at: number) => tl
    .fromTo(m.scale, { x: 0.5, y: 0.5, z: 0.5 }, { x: 2.4, y: 2.4, z: 2.4, duration: 1.3, ease: 'expo.out', immediateRender: false }, at)
    .fromTo(m.material, { opacity: 0.9 }, { opacity: 0, duration: 1.3, immediateRender: false }, at)
    .fromTo(nodes[NEPTUNE].g.scale, { x: 1.35, y: 1.35, z: 1.35 }, { x: 1, y: 1, z: 1, duration: 0.8, ease: 'back.out(3)', immediateRender: false }, at)

  const story = gsap.timeline({ repeat: -1, repeatDelay: 0.4, paused: true })
  story.set(cageMats, { opacity: (i: number) => (i ? 0.07 : 1) }, 0)
    .fromTo(cage.scale, { x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1, duration: 0.9, ease: 'back.out(2)', immediateRender: false }, 0.3)
  locked.forEach((c, k) => flyCoin(story, c, () => slot(k), 0.5, 0.9, 0.2 + k * 0.07))
  say(story, 'Locked for deal 7. No timer.', cagePos, 0.6, 1.6)
  fly(story, pk1, E, N, 2.6, 1.8, 1.4)
  pulse(story, sh1, 3.2); say(story, 'Decided once: commit', N, 3.2, 1.3)
  fly(story, pk2, E, N, 1.6, 1.8, 2.9)
  pulse(story, sh2, 4.7); say(story, 'Same answer to the copy', N, 4.7, 1.3)
  fly(story, pk1, N, E, 2.6, 1.8, 4.1)
  story.to(cage.scale, { x: 1.8, y: 1.8, z: 1.8, duration: 0.7, ease: 'power2.out' }, 5.9)
    .to(cageMats, { opacity: 0, duration: 0.7 }, 5.9)
  say(story, 'Released on commit', cagePos, 5.9, 1.6)
  locked.forEach((c, k) => {
    flyCoin(story, c, () => orbitPos({ ...c, owner: NEPTUNE, a: c.a + Math.PI / 6 }, new THREE.Vector3()), 2.2, 1.6, 6.3 + k * 0.08)
    story.call(() => { c.owner = NEPTUNE; c.a += Math.PI / 6; c.free = false }, [], 7.95 + k * 0.08)
  })
  // Quietly hand the coins back to Earth for the next loop.
  story.to(locked.map(c => c.m.scale), { x: 0, y: 0, z: 0, duration: 0.3, stagger: 0.03 }, 9.4)
    .call(() => locked.forEach((c) => { c.owner = EARTH; c.a -= Math.PI / 6 }), [], 9.95)
    .to(locked.map(c => c.m.scale), { x: 1, y: 1, z: 1, duration: 0.4, stagger: 0.03, ease: 'back.out(3)' }, 10)

  s.onTick((t, dt) => {
    coins.forEach((c) => {
      c.a += dt * 0.6
      if (!c.free) orbitPos(c, c.m.position)
      c.m.rotation.set(t + c.a, c.a, 0)
    })
    cage.rotation.y = t * 0.5; cage.rotation.x = Math.sin(t * 0.7) * 0.2
    camera.position.set(Math.sin(t * 0.12) * 1.2, 2.4, 10.8)
    camera.lookAt(0, 0.25, 0)
  })

  const intro = gsap.timeline({ paused: true })
  nodes.forEach((n, i) => intro
    .fromTo(n.g.scale, { x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1, duration: 0.7, ease: 'back.out(3)' }, i * 0.08)
    .fromTo(n.lab, { opacity: 0 }, { opacity: 0.85, duration: 0.5 }, 0.2 + i * 0.08))
  intro.call(() => { story.restart() }, [], 1.2)

  s.onEnter(() => {
    story.pause(0)
    locked.forEach((c) => { c.owner = EARTH; c.free = false; c.m.scale.setScalar(1) })
    if (s.reduced) intro.progress(1, true).pause()
    else intro.restart()
  })
  return () => story.kill()
}, { fov: 30 })
</script>

<template>
  <div ref="host" style="position:absolute; inset:0; overflow:hidden" />
</template>
