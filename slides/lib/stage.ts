// Shared Three.js stage for the animated slides: renderer, resize, render loop that runs only while the
// slide is current, HTML labels that follow 3D objects, and a few small scene helpers.
import * as THREE from 'three'
import gsap from 'gsap'
import { onMounted, onBeforeUnmount, watch, type Ref } from 'vue'
import { useIsSlideActive } from '@slidev/client'

export { THREE, gsap }

export const C = {
  night: '#18206b', deep: '#0b0f3a', ink: '#e9edfb', ink2: '#a9b2df', saffron: '#f4b41a',
  ultra: '#2a3bd1', navy: '#16224a', fog: '#eef1f6', rule: '#c9d1e0',
}

export const BODIES = [
  { name: 'Mercury', au: 0.39, ph: 0.25 }, { name: 'Venus', au: 0.72, ph: 1.15 }, { name: 'Earth', au: 1.0, ph: 2.05 },
  { name: 'Mars', au: 1.52, ph: 2.95 }, { name: 'Ceres', au: 2.77, ph: 3.85 }, { name: 'Jupiter', au: 5.2, ph: 4.75 },
  { name: 'Saturn', au: 9.58, ph: 5.65 }, { name: 'Uranus', au: 19.2, ph: 2.4 }, { name: 'Neptune', au: 30.1, ph: -0.8 },
]
export const orbitR = (au: number) => 1.1 + 1.35 * Math.log(au + 0.5)
export const bodyPos = (i: number, t: number, out = new THREE.Vector3()) => {
  const r = orbitR(BODIES[i].au), a = BODIES[i].ph + t * 0.55 * Math.pow(BODIES[i].au, -1.5)
  return out.set(Math.cos(a) * r, 0, Math.sin(a) * r)
}

let _glow: THREE.Texture | undefined
export function glowTexture() {
  if (_glow) return _glow
  const c = document.createElement('canvas'); c.width = c.height = 128
  const g = c.getContext('2d')!, grd = g.createRadialGradient(64, 64, 0, 64, 64, 64)
  grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.16, 'rgba(255,255,255,.85)')
  grd.addColorStop(0.42, 'rgba(255,255,255,.2)'); grd.addColorStop(1, 'rgba(255,255,255,0)')
  g.fillStyle = grd; g.fillRect(0, 0, 128, 128)
  return (_glow = new THREE.CanvasTexture(c))
}

export function glow(color: THREE.ColorRepresentation, size: number, opacity = 1, additive = true) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(), color, transparent: true, opacity, depthWrite: false,
    blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
  }))
  s.scale.setScalar(size)
  return s
}

/** A circle in the XZ plane. */
export function circle(r: number, color: THREE.ColorRepresentation, opacity: number, seg = 256) {
  const pts = Array.from({ length: seg + 1 }, (_, i) => {
    const a = (i / seg) * Math.PI * 2
    return new THREE.Vector3(Math.cos(a) * r, 0, Math.sin(a) * r)
  })
  const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false }))
  l.frustumCulled = false
  return l
}

/** Tween that reveals a line from its first vertex to its last. */
export function drawIn(line: THREE.Line, vars: gsap.TweenVars) {
  const total = line.geometry.attributes.position.count, p = { v: 0 }
  line.geometry.setDrawRange(0, 0)
  return gsap.fromTo(p, { v: 0 }, { v: 1, ...vars, onUpdate: () => line.geometry.setDrawRange(0, Math.floor(p.v * total)) })
}

export function starfield(n: number, r: number, color: THREE.ColorRepresentation, opacity: number) {
  const pos = new Float32Array(n * 3)
  for (let i = 0; i < n; i++) {
    const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u)
    pos.set([Math.cos(a) * s * r, u * r, Math.sin(a) * s * r], i * 3)
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  return new THREE.Points(g, new THREE.PointsMaterial({
    color, size: 0.22, map: glowTexture(), transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending,
  }))
}

/** Quadratic arc from a to b, lifted by `lift` in y at the midpoint. */
export function arc(a: THREE.Vector3, b: THREE.Vector3, lift: number) {
  const A = a.clone(), B = b.clone(), M = a.clone().add(b).multiplyScalar(0.5); M.y += lift
  return (u: number, out = new THREE.Vector3()) => {
    const v = 1 - u
    return out.set(v * v * A.x + 2 * v * u * M.x + u * u * B.x, v * v * A.y + 2 * v * u * M.y + u * u * B.y, v * v * A.z + 2 * v * u * M.z + u * u * B.z)
  }
}

/** A glowing head with a fading line trail. Move `p`; call `tick()` every frame. */
export function comet(scene: THREE.Scene, color: THREE.ColorRepresentation, size = 0.5, N = 40) {
  const c = new THREE.Color(color), pos = new Float32Array(N * 3), col = new Float32Array(N * 3)
  for (let k = 0; k < N; k++) { const f = Math.pow(1 - k / N, 1.6); col.set([c.r * f, c.g * f, c.b * f], k * 3) }
  const geo = new THREE.BufferGeometry()
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3)); geo.setAttribute('color', new THREE.BufferAttribute(col, 3))
  const trail = new THREE.Line(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }))
  trail.frustumCulled = false
  const head = glow(color, size)
  head.visible = trail.visible = false
  scene.add(trail, head)
  const hist = Array.from({ length: N }, () => new THREE.Vector3())
  const p = new THREE.Vector3()
  return {
    p, head,
    start(at: THREE.Vector3) { p.copy(at); hist.forEach(h => h.copy(at)); head.visible = trail.visible = true },
    hide() { head.visible = trail.visible = false },
    tick() {
      if (!trail.visible) return
      hist.unshift(hist.pop()!.copy(p))
      hist.forEach((h, k) => pos.set([h.x, h.y, h.z], k * 3))
      geo.attributes.position.needsUpdate = true
      head.position.copy(p)
    },
  }
}

/** A one-shot burst of particles. Call `tick(dt)` every frame. */
export function sparks(scene: THREE.Scene, color: THREE.ColorRepresentation, n = 80, additive = true) {
  const pos = new Float32Array(n * 3), vel = new Float32Array(n * 3)
  const geo = new THREE.BufferGeometry(); geo.setAttribute('position', new THREE.BufferAttribute(pos, 3))
  const mat = new THREE.PointsMaterial({
    color, size: 0.12, map: glowTexture(), transparent: true, opacity: 0, depthWrite: false,
    blending: additive ? THREE.AdditiveBlending : THREE.NormalBlending,
  })
  const pts = new THREE.Points(geo, mat); pts.frustumCulled = false; scene.add(pts)
  let life = 0
  return {
    burst(at: THREE.Vector3, speed = 1.8) {
      for (let i = 0; i < n; i++) {
        const u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, s = Math.sqrt(1 - u * u), k = speed * (0.3 + Math.random())
        pos.set([at.x, at.y, at.z], i * 3); vel.set([Math.cos(a) * s * k, u * k, Math.sin(a) * s * k], i * 3)
      }
      life = 1
    },
    tick(dt: number) {
      if (life <= 0) { mat.opacity = 0; return }
      life -= dt * 1.1; mat.opacity = Math.max(0, life)
      const drag = 1 - 2 * dt
      for (let i = 0; i < n * 3; i++) { pos[i] += vel[i] * dt; vel[i] *= drag }
      geo.attributes.position.needsUpdate = true
    },
  }
}

export interface Stage {
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  el: HTMLElement
  reduced: boolean
  onTick(f: (t: number, dt: number) => void): void
  /** Runs each time the slide becomes the current one. */
  onEnter(f: () => void): void
  /** An HTML label that follows a 3D object. */
  label(text: string, obj: THREE.Object3D, style?: string, dx?: number, dy?: number, center?: boolean): HTMLSpanElement
}

export function useStage(
  host: Ref<HTMLElement | undefined>,
  setup: (s: Stage) => void | (() => void),
  opts: { fov?: number; shiftX?: number } = {},
) {
  const active = useIsSlideActive()
  let stop = () => {}
  onMounted(() => {
    const el = host.value!
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
    renderer.setPixelRatio(2)
    renderer.domElement.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block'
    el.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(opts.fov ?? 35, 1, 0.05, 400)
    const resize = () => {
      const w = el.clientWidth || 1, h = el.clientHeight || 1
      renderer.setSize(w, h, false); camera.aspect = w / h
      if (opts.shiftX) camera.setViewOffset(w, h, -w * opts.shiftX, 0, w, h)
      camera.updateProjectionMatrix()
    }
    const ro = new ResizeObserver(resize); ro.observe(el); resize()

    const ticks: ((t: number, dt: number) => void)[] = [], enters: (() => void)[] = []
    const tracked: { el: HTMLElement; obj: THREE.Object3D; dx: number; dy: number; c: string }[] = []
    const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches
    const s: Stage = {
      scene, camera, el, reduced,
      onTick: f => ticks.push(f),
      onEnter: f => enters.push(f),
      label(text, obj, style = '', dx = 10, dy = -9, center = false) {
        const sp = document.createElement('span')
        sp.textContent = text
        sp.style.cssText = `position:absolute;left:0;top:0;pointer-events:none;white-space:nowrap;will-change:transform;font:500 14px 'Archivo Variable',sans-serif;${style}`
        el.appendChild(sp)
        tracked.push({ el: sp, obj, dx, dy, c: center ? ' translateX(-50%)' : '' })
        return sp
      },
    }

    const ctx = gsap.context(() => {})
    let cleanup: void | (() => void)
    ctx.add(() => { cleanup = setup(s) })

    const v = new THREE.Vector3()
    let raf = 0, last = 0, t = 0, running = false
    const loop = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.05); last = now
      if (!reduced) t += dt
      for (const f of ticks) f(t, reduced ? 0 : dt)
      const w = el.clientWidth, h = el.clientHeight
      for (const L of tracked) {
        L.obj.getWorldPosition(v).project(camera)
        L.el.style.transform = `translate(${(v.x * 0.5 + 0.5) * w + L.dx}px,${(-v.y * 0.5 + 0.5) * h + L.dy}px)${L.c}`
        L.el.style.visibility = v.z < 1 && L.obj.visible ? '' : 'hidden'
      }
      renderer.render(scene, camera)
      raf = requestAnimationFrame(loop)
    }
    const start = () => {
      if (running) return
      running = true; last = performance.now(); raf = requestAnimationFrame(loop)
      enters.forEach(f => f())
    }
    const pause = () => { running = false; cancelAnimationFrame(raf) }
    const unwatch = watch(active, a => (a ? start() : pause()), { immediate: true })

    stop = () => {
      unwatch(); pause(); ro.disconnect()
      cleanup?.(); ctx.revert()
      scene.traverse((o: any) => {
        o.geometry?.dispose?.()
        const m = o.material; (Array.isArray(m) ? m : [m]).forEach((x: any) => x?.dispose?.())
      })
      renderer.dispose(); renderer.forceContextLoss(); el.replaceChildren()
    }
  })
  onBeforeUnmount(() => stop())
}
