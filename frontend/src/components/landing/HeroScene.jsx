import { useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * The hero's WebGL scene.
 *
 * Four particle clusters — one per source system (TMS, SMMS, TDMS, COA) —
 * start scattered like a loose network map, drift out to four corners of
 * frame, then sweep back inward and settle onto the surface of a globe as a
 * shell of light. The globe itself fades in as they arrive, already carrying
 * a set of small station lights that blink independently. Once formed, the
 * whole thing rotates slowly and the camera drifts gently with the pointer —
 * it never fully stops moving, which is the point: this is meant to feel
 * alive, not like a diagram that finished playing. The whole formation runs
 * in well under 3 seconds so the payoff — and the page around it — arrives
 * quickly rather than making people wait through a title sequence.
 *
 * Everything is points and thin lines, no heavy meshes or postprocessing, and
 * the per-frame particle update is plain array math with no allocation, so it
 * holds frame rate on integrated graphics during a live demo.
 */

const COUNT = 950
const CLUSTER_COUNT = 4
const CLUSTER_COLORS = ['#F2A93B', '#4FC3A1', '#8B9DFF', '#5FD6E8']
const GLOBE_RADIUS = 1.85
const STATION_COUNT = 42

const HOMES = [
  [-4.8, 1.8, -1.2],
  [4.8, 1.8, 1.2],
  [-4.8, -1.8, 1.2],
  [4.8, -1.8, -1.2],
]

function smoothstep(a, b, x) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)))
  return t * t * (3 - 2 * t)
}

function buildField() {
  const base = new Float32Array(COUNT * 3)
  const shell = new Float32Array(COUNT * 3) // final resting point, on the globe surface
  const cluster = new Int32Array(COUNT)
  const seed = new Float32Array(COUNT)
  const colors = new Float32Array(COUNT * 3)

  for (let i = 0; i < COUNT; i++) {
    const r = Math.pow(Math.random(), 0.55) * 5.6
    const theta = Math.random() * Math.PI * 2
    const y = (Math.random() - 0.5) * 2.3
    base[i * 3] = Math.cos(theta) * r
    base[i * 3 + 1] = y
    base[i * 3 + 2] = Math.sin(theta) * r

    // Even-ish coverage of the sphere via a golden-angle spiral, per particle
    // rather than per station — this is the shell, not the lights.
    const gy = 1 - (i / (COUNT - 1)) * 2
    const gr = Math.sqrt(Math.max(0, 1 - gy * gy))
    const gtheta = 2.399963 * i
    const sx = Math.cos(gtheta) * gr
    const sy = gy
    const sz = Math.sin(gtheta) * gr
    const jitterR = GLOBE_RADIUS * (1.01 + Math.random() * 0.05)
    shell[i * 3] = sx * jitterR
    shell[i * 3 + 1] = sy * jitterR
    shell[i * 3 + 2] = sz * jitterR

    const c = i % CLUSTER_COUNT
    cluster[i] = c
    seed[i] = Math.random() * Math.PI * 2

    const col = new THREE.Color(CLUSTER_COLORS[c])
    colors[i * 3] = col.r
    colors[i * 3 + 1] = col.g
    colors[i * 3 + 2] = col.b
  }
  return { base, shell, cluster, seed, colors }
}

function Field({ reduce }) {
  const { base, shell, cluster, seed, colors } = useMemo(buildField, [])
  const positions = useMemo(() => base.slice(), [base])
  const pointsRef = useRef()
  const geomRef = useRef()
  const t0 = useRef(null)

  useFrame((state) => {
    const posAttr = geomRef.current?.attributes.position
    if (!posAttr) return

    if (reduce) {
      posAttr.array.set(shell)
      posAttr.needsUpdate = true
      return
    }

    if (t0.current === null) t0.current = state.clock.elapsedTime
    const t = state.clock.elapsedTime - t0.current

    const outT = smoothstep(0.25, 1.05, t)
    const inT = smoothstep(1.3, 2.35, t)

    for (let i = 0; i < COUNT; i++) {
      const ix = i * 3
      const c = cluster[i]
      const j = seed[i]

      let x = base[ix] + (HOMES[c][0] - base[ix]) * outT
      let y = base[ix + 1] + (HOMES[c][1] - base[ix + 1]) * outT
      let z = base[ix + 2] + (HOMES[c][2] - base[ix + 2]) * outT

      x += Math.sin(t * 0.6 + j) * 0.06
      y += Math.cos(t * 0.5 + j) * 0.06

      positions[ix] = x + (shell[ix] - x) * inT
      positions[ix + 1] = y + (shell[ix + 1] - y) * inT
      positions[ix + 2] = z + (shell[ix + 2] - z) * inT
    }

    posAttr.array.set(positions)
    posAttr.needsUpdate = true
  })

  return (
    <points ref={pointsRef}>
      <bufferGeometry ref={geomRef}>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[colors, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.05}
        vertexColors
        transparent
        opacity={0.9}
        sizeAttenuation
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  )
}

const STATION_VERTEX = `
  attribute float aPhase;
  varying float vPhase;
  uniform float uFade;
  void main() {
    vPhase = aPhase;
    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    gl_PointSize = (58.0 / -mvPosition.z) * (0.4 + 0.6 * uFade);
    gl_Position = projectionMatrix * mvPosition;
  }
`

const STATION_FRAGMENT = `
  varying float vPhase;
  uniform float uTime;
  uniform float uFade;
  uniform vec3 uColor;
  void main() {
    float blink = 0.3 + 0.7 * pow(0.5 + 0.5 * sin(uTime * 1.7 + vPhase), 3.0);
    float d = length(gl_PointCoord - vec2(0.5));
    float disc = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(uColor, disc * blink * uFade);
  }
`

function stationGeometry() {
  const positions = new Float32Array(STATION_COUNT * 3)
  const phases = new Float32Array(STATION_COUNT)
  for (let i = 0; i < STATION_COUNT; i++) {
    const y = 1 - (i / (STATION_COUNT - 1)) * 2
    const r = Math.sqrt(Math.max(0, 1 - y * y))
    const theta = 2.399963 * i * 1.9
    const rad = GLOBE_RADIUS * 1.012
    positions[i * 3] = Math.cos(theta) * r * rad
    positions[i * 3 + 1] = y * rad
    positions[i * 3 + 2] = Math.sin(theta) * r * rad
    phases[i] = Math.random() * Math.PI * 2
  }
  return { positions, phases }
}

function Globe({ reduce }) {
  const wireRef = useRef()
  const glowRef = useRef()
  const stationMatRef = useRef()
  const t0 = useRef(null)
  const { positions, phases } = useMemo(stationGeometry, [])

  const uniforms = useMemo(
    () => ({
      uTime: { value: 0 },
      uFade: { value: reduce ? 1 : 0 },
      uColor: { value: new THREE.Color('#CFE3F2') },
    }),
    [reduce]
  )

  useFrame((state) => {
    if (t0.current === null) t0.current = state.clock.elapsedTime
    const t = state.clock.elapsedTime - t0.current
    const fade = reduce ? 1 : smoothstep(1.65, 2.55, t)

    if (wireRef.current) wireRef.current.material.opacity = fade * 0.4
    if (glowRef.current) glowRef.current.material.opacity = fade * 0.05
    if (stationMatRef.current) {
      stationMatRef.current.uniforms.uTime.value = state.clock.elapsedTime
      stationMatRef.current.uniforms.uFade.value = fade
    }
  })

  return (
    <group>
      <mesh ref={wireRef}>
        <icosahedronGeometry args={[GLOBE_RADIUS, 3]} />
        <meshBasicMaterial color="#4A6478" wireframe transparent opacity={0} depthWrite={false} />
      </mesh>
      <mesh ref={glowRef} scale={1.06}>
        <sphereGeometry args={[GLOBE_RADIUS, 32, 32]} />
        <meshBasicMaterial
          color="#CFE3F2"
          transparent
          opacity={0}
          side={THREE.BackSide}
          depthWrite={false}
        />
      </mesh>
      <points>
        <bufferGeometry>
          <bufferAttribute attach="attributes-position" args={[positions, 3]} />
          <bufferAttribute attach="attributes-aPhase" args={[phases, 1]} />
        </bufferGeometry>
        <shaderMaterial
          ref={stationMatRef}
          uniforms={uniforms}
          vertexShader={STATION_VERTEX}
          fragmentShader={STATION_FRAGMENT}
          transparent
          depthWrite={false}
          blending={THREE.AdditiveBlending}
        />
      </points>
    </group>
  )
}

function Scene({ reduce }) {
  const groupRef = useRef()
  const pointer = useRef({ x: 0, y: 0 })

  useFrame((state, delta) => {
    if (!reduce && groupRef.current) {
      groupRef.current.rotation.y += delta * 0.05
    }
    // Gentle parallax toward the pointer, never enough to disorient.
    pointer.current.x += (state.pointer.x - pointer.current.x) * 0.03
    pointer.current.y += (state.pointer.y - pointer.current.y) * 0.03
    state.camera.position.x = pointer.current.x * 0.6
    state.camera.position.y = pointer.current.y * 0.35
    state.camera.lookAt(0, 0, 0)
  })

  return (
    <group ref={groupRef}>
      <Field reduce={reduce} />
      <Globe reduce={reduce} />
    </group>
  )
}

export default function HeroScene({ reduce = false }) {
  return (
    <div className="pointer-events-none absolute inset-0">
      <Canvas
        dpr={[1, 1.6]}
        camera={{ position: [0, 0, 9.2], fov: 42 }}
        gl={{ antialias: true, alpha: true, powerPreference: 'low-power' }}
      >
        <Scene reduce={reduce} />
      </Canvas>
    </div>
  )
}
