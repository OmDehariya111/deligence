"use client";

import { Suspense, useMemo, useRef, useState, useEffect } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { EffectComposer, Bloom } from "@react-three/postprocessing";
import * as THREE from "three";



const COLOR_GREEN = new THREE.Color("#39ff88");
const COLOR_GREEN_BRIGHT = new THREE.Color("#7bffb5");
const COLOR_CYAN = new THREE.Color("#22e0ff");

// Build a soft radial sprite for particle texture (glowy dot)
function makeSpriteTexture() {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.25, "rgba(255,255,255,0.85)");
  g.addColorStop(0.55, "rgba(255,255,255,0.25)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

type ParticleData = {
  positions: Float32Array;
  colors: Float32Array;
  baseColors: Float32Array;
  sizes: Float32Array;
  basePos: Float32Array; // rest positions for cursor scatter
  orbit: Float32Array; // per particle: radius, angle, ySpeed, drift
  flicker: Float32Array; // per particle flicker seed
};

function buildGalaxy(count: number): ParticleData {
  const positions = new Float32Array(count * 3);
  const basePos = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const baseColors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const orbit = new Float32Array(count * 4);
  const flicker = new Float32Array(count * 2);

  const arms = 3;
  const armSpread = 0.55;
  const armTwist = 2.4;

  for (let i = 0; i < count; i++) {
    // radius biased toward center
    const r = Math.pow(Math.random(), 1.7) * 3.8 + 0.15;
    const arm = i % arms;
    const armAngle = (arm / arms) * Math.PI * 2;
    const angle = armAngle + r * armTwist + (Math.random() - 0.5) * armSpread;
    // flatten Y (galaxy disk) with small puff
    const puff = (Math.random() - 0.5) * (0.5 - Math.min(0.4, r * 0.08));
    const y = puff * (1 - r / 5) + (Math.random() - 0.5) * 0.15;
    const x = Math.cos(angle) * r;
    const z = Math.sin(angle) * r;

    positions[i * 3] = x;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = z;
    basePos[i * 3] = x;
    basePos[i * 3 + 1] = y;
    basePos[i * 3 + 2] = z;

    const isCyan = Math.random() < 0.2;
    const base = isCyan ? COLOR_CYAN : Math.random() < 0.3 ? COLOR_GREEN_BRIGHT : COLOR_GREEN;
    // brighter near center
    const b = 0.6 + Math.max(0, 1 - r / 3.5) * 0.6;
    const rCol = base.r * b;
    const gCol = base.g * b;
    const bCol = base.b * b;

    colors[i * 3] = rCol;
    colors[i * 3 + 1] = gCol;
    colors[i * 3 + 2] = bCol;
    
    baseColors[i * 3] = rCol;
    baseColors[i * 3 + 1] = gCol;
    baseColors[i * 3 + 2] = bCol;

    sizes[i] = 0.02 + Math.random() * 0.05 + (r < 1 ? 0.02 : 0);

    orbit[i * 4] = r; // radius
    orbit[i * 4 + 1] = angle; // start angle
    orbit[i * 4 + 2] = 0; // angular speed (0 to preserve exact spiral shape)
    orbit[i * 4 + 3] = Math.random() * Math.PI * 2; // y drift phase

    flicker[i * 2] = Math.random() * Math.PI * 2;
    flicker[i * 2 + 1] = 0.5 + Math.random() * 1.2;
  }

  return { positions, colors, baseColors, sizes, basePos, orbit, flicker };
}

function ParticleField({
  count,
  cursorRef,
  timeRef,
  reactive,
}: {
  count: number;
  cursorRef: React.MutableRefObject<{ x: number; y: number; z: number; active: boolean }>;
  timeRef: React.MutableRefObject<number>;
  reactive: boolean;
}) {
  const ref = useRef<THREE.Points>(null!);
  const tex = useMemo(() => makeSpriteTexture(), []);
  const data = useMemo(() => buildGalaxy(count), [count]);

  useFrame((_, dt) => {
    const t = timeRef.current;
    const pts = ref.current;
    if (!pts) return;
    const posAttr = pts.geometry.attributes.position as THREE.BufferAttribute;
    const colAttr = pts.geometry.attributes.color as THREE.BufferAttribute;
    const arr = posAttr.array as Float32Array;
    const cols = colAttr.array as Float32Array;
    const cx = cursorRef.current.x;
    const cy = cursorRef.current.y;
    const cz = cursorRef.current.z;
    const active = cursorRef.current.active && reactive;

    for (let i = 0; i < count; i++) {
      const r = data.orbit[i * 4];
      const a0 = data.orbit[i * 4 + 1];
      const speed = data.orbit[i * 4 + 2];
      const yPh = data.orbit[i * 4 + 3];
      const a = a0 + t * speed;
      let x = Math.cos(a) * r;
      let z = Math.sin(a) * r;
      let y = data.basePos[i * 3 + 1] + Math.sin(t * 0.4 + yPh) * 0.05;

      if (active) {
        const dx = x - cx;
        const dy = y - cy;
        const dz = z - cz;
        const d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 0.7) {
          const f = (0.7 - d2) * 0.6;
          const inv = 1 / (Math.sqrt(d2) + 0.001);
          x += dx * inv * f;
          y += dy * inv * f;
          z += dz * inv * f;
        }
      }

      arr[i * 3] = x;
      arr[i * 3 + 1] = y;
      arr[i * 3 + 2] = z;

      // flicker brightness
      const fPh = data.flicker[i * 2];
      const fSp = data.flicker[i * 2 + 1];
      const fl = 0.75 + 0.35 * (0.5 + 0.5 * Math.sin(t * fSp + fPh));
      // reset from base color scaled
      const bi = i * 3;
      // read from unmodified baseColors
      cols[bi] = data.baseColors[bi] * fl;
      cols[bi + 1] = data.baseColors[bi + 1] * fl;
      cols[bi + 2] = data.baseColors[bi + 2] * fl;
    }
    posAttr.needsUpdate = true;
    colAttr.needsUpdate = true;
    void dt;
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[data.positions, 3]} />
        <bufferAttribute attach="attributes-color" args={[data.colors, 3]} />
        <bufferAttribute attach="attributes-size" args={[data.sizes, 1]} />
      </bufferGeometry>
      <pointsMaterial
        map={tex}
        size={0.09}
        sizeAttenuation
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        vertexColors
        alphaTest={0.001}
      />
    </points>
  );
}


function GalaxySystem({
  count,
}: {
  count: number;
}) {
  const group = useRef<THREE.Group>(null!);
  const timeRef = useRef(0);
  const cursorRef = useRef({ x: 0, y: 0, z: 0, active: false });

  useFrame((_, dt) => {
    timeRef.current += dt;
    if (!group.current) return;
    // Constant slow rotation with a fixed tilt for a nice angled view
    group.current.rotation.x = 0.45;
    group.current.rotation.y += dt * 0.08;
  });

  return (
    <group ref={group} scale={[1, 0.55, 1]}>
      <ParticleField count={count} cursorRef={cursorRef} timeRef={timeRef} reactive={false} />
    </group>
  );
}

function FallbackOrb() {
  return (
    <div className="relative flex h-full w-full items-center justify-center">
      <div className="absolute h-64 w-64 rounded-full bg-primary/20 blur-3xl" />
      <div className="relative h-40 w-40 rounded-full border border-primary/30 bg-gradient-to-br from-primary/20 to-transparent shadow-[0_0_80px_rgba(57,255,136,0.3)]" />
    </div>
  );
}

export function NeuralOrb() {
  const [supported, setSupported] = useState(true);
  const [isLowPower, setIsLowPower] = useState(false);

  useEffect(() => {
    try {
      const c = document.createElement("canvas");
      const gl = c.getContext("webgl2") || c.getContext("webgl");
      if (!gl) setSupported(false);
    } catch {
      setSupported(false);
    }
    const mobile =
      window.matchMedia("(max-width: 768px)").matches ||
      (navigator as Navigator & { deviceMemory?: number }).deviceMemory !== undefined &&
        ((navigator as Navigator & { deviceMemory?: number }).deviceMemory as number) <= 4;
    setIsLowPower(mobile);
  }, []);

  if (!supported) return <FallbackOrb />;

  const count = isLowPower ? 1200 : 4200;

  return (
    <div className="relative h-full w-full">
      <Canvas
        dpr={[1, isLowPower ? 1.25 : 1.75]}
        camera={{ position: [0, 1.2, 8], fov: 45 }}
        gl={{ antialias: true, alpha: true, premultipliedAlpha: false }}
        style={{ background: "transparent" }}
      >
        <Suspense fallback={null}>
          <GalaxySystem count={count} />
          {!isLowPower && (
            <EffectComposer>
              <Bloom
                intensity={1.15}
                luminanceThreshold={0.08}
                luminanceSmoothing={0.9}
                mipmapBlur
              />
            </EffectComposer>
          )}
        </Suspense>
      </Canvas>
    </div>
  );
}