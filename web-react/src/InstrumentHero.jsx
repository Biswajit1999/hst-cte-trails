import { useEffect, useRef, useState } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';

function useReducedMotion() {
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    update();
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return reduced;
}

function FrameTicker({ active }) {
  const invalidate = useThree((state) => state.invalidate);

  useEffect(() => {
    invalidate();
    if (!active) return undefined;
    const timer = window.setInterval(invalidate, 80);
    return () => window.clearInterval(timer);
  }, [active, invalidate]);

  return null;
}

function SolarPanel({ position }) {
  const cells = [];
  for (let row = -1; row <= 1; row += 1) {
    for (let column = -2; column <= 2; column += 1) {
      cells.push(
        <mesh key={`${row}-${column}`} position={[position[0], position[1] + row * 0.31, position[2] + column * 0.3]}>
          <boxGeometry args={[0.05, 0.25, 0.25]} />
          <meshStandardMaterial color="#1d4ed8" roughness={0.52} metalness={0.22} />
        </mesh>,
      );
    }
  }
  return <group>{cells}</group>;
}

function ChargeTrail({ position, scale, opacity }) {
  return (
    <mesh position={position} scale={scale}>
      <boxGeometry args={[1, 1, 1]} />
      <meshBasicMaterial color="#60a5fa" transparent opacity={opacity} />
    </mesh>
  );
}

function InstrumentModel({ animate }) {
  const model = useRef(null);

  useFrame((state, delta) => {
    if (!model.current || !animate) return;
    model.current.rotation.y += delta * 0.16;
    model.current.position.y = Math.sin(state.clock.elapsedTime * 0.55) * 0.08;
  });

  return (
    <group ref={model} rotation={[0.18, -0.55, -0.08]}>
      <group rotation={[0, 0, Math.PI / 2]}>
        <mesh>
          <cylinderGeometry args={[0.7, 0.76, 2.7, 12]} />
          <meshStandardMaterial color="#9aa8ba" roughness={0.48} metalness={0.68} />
        </mesh>
        <mesh position={[0, 1.37, 0]}>
          <cylinderGeometry args={[0.74, 0.74, 0.12, 18]} />
          <meshStandardMaterial color="#27364a" roughness={0.35} metalness={0.72} />
        </mesh>
        <mesh position={[0, 1.46, 0]}>
          <torusGeometry args={[0.49, 0.09, 8, 24]} />
          <meshStandardMaterial color="#d6e1ee" roughness={0.35} metalness={0.8} />
        </mesh>
        <mesh position={[0, 1.49, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <circleGeometry args={[0.41, 24]} />
          <meshStandardMaterial color="#07111f" roughness={0.2} metalness={0.35} />
        </mesh>
      </group>

      <mesh position={[0, -1.5, 0]}>
        <boxGeometry args={[0.9, 0.42, 0.95]} />
        <meshStandardMaterial color="#334155" roughness={0.42} metalness={0.66} />
      </mesh>

      <mesh position={[0, -1.76, 0]} rotation={[-0.08, 0, 0]}>
        <boxGeometry args={[1.3, 0.08, 1.15]} />
        <meshStandardMaterial color="#0f2849" emissive="#1d4ed8" emissiveIntensity={0.13} roughness={0.4} metalness={0.5} />
      </mesh>

      <SolarPanel position={[0, 0.05, 1.25]} />
      <SolarPanel position={[0, 0.05, -1.25]} />
      <mesh position={[0, 0.05, 0]}>
        <boxGeometry args={[0.09, 0.09, 3.4]} />
        <meshStandardMaterial color="#91a4ba" roughness={0.4} metalness={0.72} />
      </mesh>

      <group position={[0.72, -1.72, 0.15]}>
        <ChargeTrail position={[0, 0.34, 0]} scale={[0.04, 0.28, 0.05]} opacity={0.66} />
        <ChargeTrail position={[0, 0.65, 0]} scale={[0.035, 0.2, 0.045]} opacity={0.48} />
        <ChargeTrail position={[0, 0.89, 0]} scale={[0.03, 0.13, 0.04]} opacity={0.3} />
      </group>
    </group>
  );
}

export default function InstrumentHero() {
  const reducedMotion = useReducedMotion();

  return (
    <figure className="relative h-full w-full" aria-label="Procedural Hubble-like detector instrument illustration">
      <Canvas
        camera={{ position: [5.4, 3.1, 6.4], fov: 37 }}
        dpr={[1, 1.5]}
        frameloop="demand"
        gl={{ antialias: false, alpha: true, powerPreference: 'low-power' }}
      >
        <FrameTicker active={!reducedMotion} />
        <ambientLight intensity={1.15} />
        <directionalLight position={[5, 6, 4]} intensity={2.2} color="#dbeafe" />
        <pointLight position={[-4, -2, 3]} intensity={1.1} color="#3b82f6" />
        <InstrumentModel animate={!reducedMotion} />
      </Canvas>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-4 bg-gradient-to-t from-slate-950 via-slate-950/80 to-transparent px-4 pb-4 pt-14">
        <div>
          <p className="instrument-label">Optical assembly / detector plane</p>
          <p className="mt-1 text-xs text-slate-400">Procedural low-poly instrument schematic</p>
        </div>
        <figcaption className="max-w-40 text-right text-[0.65rem] uppercase tracking-[0.12em] text-blue-200/80">
          Stylized illustration, not flight data
        </figcaption>
      </div>
    </figure>
  );
}
