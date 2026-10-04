<script setup lang="ts">
// "The problem": light leaves Earth as an expanding front, lighting each settlement as it passes,
// and needs 4.2 h to reach Neptune.
import { ref } from 'vue'
import { useStage, THREE, gsap, C, BODIES, orbitR, bodyPos, glow, circle, drawIn, starfield } from '../lib/stage'

const host = ref<HTMLDivElement>()
const EARTH = 2, NEPTUNE = 8, RMAX = 9

useStage(host, (s) => {
  const { scene, camera } = s
  scene.add(starfield(1400, 70, C.ink, 0.5))
  const sun = glow(C.saffron, 1.6, 0.9), sunCore = glow('#fff4d6', 0.45)
  scene.add(sun, sunCore)

  const orbits = BODIES.map(b => { const o = circle(orbitR(b.au), C.ink, 0.18); o.geometry.setDrawRange(0, 0); scene.add(o); return o })
  const planets = BODIES.map((b, i) => {
    const hot = i === EARTH || i === NEPTUNE
    const g = new THREE.Group()
    g.add(new THREE.Mesh(new THREE.SphereGeometry(hot ? 0.1 : 0.06, 20, 20), new THREE.MeshBasicMaterial({ color: hot ? C.saffron : C.ink })))
    const halo = glow(hot ? C.saffron : C.ink, hot ? 1 : 0.5, hot ? 0.9 : 0.45)
    g.add(halo); g.scale.setScalar(0); scene.add(g)
    const lab = s.label(b.name, g, `color:${hot ? C.saffron : C.ink2};font-weight:${hot ? 700 : 400};opacity:0`)
    return { g, halo, lab, base: halo.scale.x, lit: false }
  })

  // The wavefront: a thin bright edge with a soft wake, lying in the orbital plane.
  const u = { uR: { value: 0 }, uO: { value: 0 }, uC: { value: new THREE.Color(C.saffron) } }
  const wave = new THREE.Mesh(new THREE.PlaneGeometry(RMAX * 2, RMAX * 2), new THREE.ShaderMaterial({
    uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: 'varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.); }',
    fragmentShader: `varying vec2 vUv; uniform float uR, uO; uniform vec3 uC;
      void main(){
        float d = length(vUv - .5) * 2.;
        float edge = exp(-pow((d - uR) / .005, 2.));
        float wake = step(d, uR) * smoothstep(uR - .18, uR, d) * .14;
        float a = (edge + wake) * uO * smoothstep(1., .92, d);
        gl_FragColor = vec4(uC, a);
      }`,
  }))
  wave.rotation.x = -Math.PI / 2
  scene.add(wave)

  const link = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineBasicMaterial({ color: C.saffron, transparent: true, opacity: 0 }))
  link.frustumCulled = false
  scene.add(link)
  const front = new THREE.Object3D(); scene.add(front)
  const readout = s.label('', front, `color:${C.saffron};font-weight:700;font-size:17px;opacity:0`, 12, -28)

  const origin = new THREE.Vector3(), dir = new THREE.Vector3(), p = new THREE.Vector3()
  const st = { r: 0, D: 1, live: false }
  let now = 0, cur: gsap.core.Timeline | undefined

  const flash = (pl: typeof planets[number], big: boolean) => {
    gsap.fromTo(pl.halo.scale, { x: pl.base * (big ? 7 : 3.4), y: pl.base * (big ? 7 : 3.4) },
      { x: pl.base, y: pl.base, duration: big ? 1.8 : 1.1, ease: 'expo.out' })
    gsap.fromTo(pl.lab, { opacity: 1 }, { opacity: 0.8, duration: 1.4 })
  }

  const pulse = () => {
    bodyPos(EARTH, now, origin)
    bodyPos(NEPTUNE, now + 4.2, p)
    st.D = p.distanceTo(origin); dir.subVectors(p, origin).normalize()
    wave.position.copy(origin)
    planets.forEach(pl => (pl.lit = false))
    planets[EARTH].lit = true; flash(planets[EARTH], false)
    cur?.kill()
    cur = gsap.timeline()
      .set(st, { r: 0, live: true }).set(u.uO, { value: 1 })
      .to(readout, { opacity: 1, duration: 0.3 }, 0)
      .to(st, { r: st.D, duration: 4.2, ease: 'none' }, 0)
      .to(link.material, { opacity: 0.75, duration: 0.3 }, 4.2)
      .to(st, { r: st.D * 1.3, duration: 1.5, ease: 'none' }, 4.2)
      .to(u.uO, { value: 0, duration: 1.5, ease: 'power2.out' }, 4.2)
      .to(readout, { opacity: 0, duration: 0.5 }, 5.2)
      .set(st, { live: false }, 5.7)
      .to(link.material, { opacity: 0, duration: 1 }, 5.8)
  }

  const rig = { dist: 48, el: 0.2 }
  s.onTick((t) => {
    now = t
    planets.forEach((pl, i) => {
      bodyPos(i, t, pl.g.position)
      if (st.live && !pl.lit && pl.g.position.distanceTo(origin) <= st.r) {
        pl.lit = true; flash(pl, i === NEPTUNE)
        if (i === NEPTUNE) {
          pl.lab.textContent = 'Neptune, 4.2 h later'
          gsap.delayedCall(2.6, () => { pl.lab.textContent = 'Neptune' })
        }
      }
    })
    u.uR.value = st.r / RMAX
    front.position.copy(origin).addScaledVector(dir, Math.min(st.r, st.D))
    readout.textContent = `h ${(4.2 * Math.min(st.r / st.D, 1)).toFixed(1)}`
    const lp = link.geometry.attributes.position as THREE.BufferAttribute
    const np = planets[NEPTUNE].g.position
    lp.setXYZ(0, origin.x, origin.y, origin.z); lp.setXYZ(1, np.x, np.y, np.z); lp.needsUpdate = true
    const az = Math.sin(t * 0.07) * 0.35
    camera.position.set(Math.sin(az) * rig.dist * Math.sin(rig.el), rig.dist * Math.cos(rig.el), Math.cos(az) * rig.dist * Math.sin(rig.el))
    camera.lookAt(0, 0, 0)
    sun.material.opacity = 0.8 + Math.sin(t * 2) * 0.1
  })

  const loop = gsap.timeline({ repeat: -1, paused: true }).call(pulse).to({}, { duration: 7.4 })
  const intro = gsap.timeline({ paused: true })
    .fromTo(rig, { dist: 48, el: 0.2 }, { dist: 22.5, el: 0.85, duration: 4, ease: 'power3.inOut' }, 0)
    .fromTo(sun.scale, { x: 0, y: 0 }, { x: 1.6, y: 1.6, duration: 1.4, ease: 'expo.out' }, 0)
  orbits.forEach((o, i) => intro.add(drawIn(o, { duration: 1.6, ease: 'power2.inOut' }), 0.3 + i * 0.12))
  planets.forEach((pl, i) => intro
    .fromTo(pl.g.scale, { x: 0, y: 0, z: 0 }, { x: 1, y: 1, z: 1, duration: 0.8, ease: 'back.out(3)' }, 0.9 + i * 0.12)
    .fromTo(pl.lab, { opacity: 0 }, { opacity: 0.8, duration: 0.6 }, 1.2 + i * 0.12))
  intro.call(() => { loop.restart() }, [], 3.4)

  s.onEnter(() => {
    loop.pause(0); cur?.kill(); st.live = false; u.uO.value = 0
    if (s.reduced) intro.progress(1, true).pause()
    else intro.restart()
  })
  return () => { cur?.kill(); loop.kill() }
}, { fov: 32, shiftX: 0.17 })
</script>

<template>
  <div ref="host" style="position:absolute; inset:0; overflow:hidden" />
</template>
