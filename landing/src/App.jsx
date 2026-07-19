import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

// ============================================================================
// 1. SCRAMBLE TEXT COMPONENTS (Hover & Scroll-Intersect)
// ============================================================================
function ScrambleText({ text }) {
  const [displayText, setDisplayText] = useState(text);
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%";
  const intervalRef = useRef(null);

  const startScramble = () => {
    let iteration = 0;
    clearInterval(intervalRef.current);
    intervalRef.current = setInterval(() => {
      setDisplayText(
        text
          .split("")
          .map((char, index) => {
            if (char === " ") return " ";
            if (index < iteration) return text[index];
            return chars[Math.floor(Math.random() * chars.length)];
          })
          .join("")
      );
      if (iteration >= text.length) clearInterval(intervalRef.current);
      iteration += 0.6;
    }, 30);
  };

  const stopScramble = () => {
    clearInterval(intervalRef.current);
    setDisplayText(text);
  };

  return (
    <span onMouseEnter={startScramble} onMouseLeave={stopScramble} className="font-mono">
      {displayText}
    </span>
  );
}

function ScrambleInHeader({ text, className }) {
  const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789#@$%";
  const getPlaceholder = () =>
    text.split("").map(char => char === " " ? " " : chars[Math.floor(Math.random() * chars.length)]).join("");

  const [displayText, setDisplayText] = useState(getPlaceholder);
  const ref = useRef(null);
  const intervalRef = useRef(null);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        let iteration = 0;
        clearInterval(intervalRef.current);
        intervalRef.current = setInterval(() => {
          setDisplayText(
            text
              .split("")
              .map((char, index) => {
                if (char === " ") return " ";
                if (index < iteration) return text[index];
                return chars[Math.floor(Math.random() * chars.length)];
              })
              .join("")
          );
          if (iteration >= text.length) {
            clearInterval(intervalRef.current);
            setDisplayText(text);
          }
          iteration += 0.6;
        }, 30);
      } else {
        clearInterval(intervalRef.current);
        setDisplayText(getPlaceholder());
      }
    }, { threshold: 0.1 });

    if (ref.current) observer.observe(ref.current);
    return () => {
      observer.disconnect();
      clearInterval(intervalRef.current);
    };
  }, [text]);

  return <span ref={ref} className={`inline-block ${className}`}>{displayText}</span>;
}

// ============================================================================
// 2. REACTIVE HOLOGRAPHIC WAVEFORM
// ============================================================================
function AudioWaveform({ state }) {
  const pathRef1 = useRef(null);
  const pathRef2 = useRef(null);
  const isListening = state === "LISTENING";
  const isSpeaking = state === "SPEAKING";

  useEffect(() => {
    let animId;
    let phase = 0;

    const updateWave = () => {
      phase += (isListening || isSpeaking) ? 0.25 : 0.06;
      
      const width = 320;
      const points1 = [];
      const points2 = [];
      
      const amplitude = (isListening || isSpeaking) ? 14 : 1.5;
      const frequency = (isListening || isSpeaking) ? 0.075 : 0.02;

      for (let x = 0; x <= width; x += 8) {
        const envelope = Math.sin((x / width) * Math.PI);
        const y1 = Math.sin(x * frequency + phase) * amplitude * envelope + 20;
        const y2 = Math.cos(x * frequency * 0.8 - phase) * (amplitude * 0.7) * envelope + 20;
        points1.push(`${x},${y1}`);
        points2.push(`${x},${y2}`);
      }

      if (pathRef1.current) {
        pathRef1.current.setAttribute('d', `M 0,20 Q ${points1.join(' ')} L 320,20`);
      }
      if (pathRef2.current) {
        pathRef2.current.setAttribute('d', `M 0,20 Q ${points2.join(' ')} L 320,20`);
      }

      animId = requestAnimationFrame(updateWave);
    };

    updateWave();
    return () => cancelAnimationFrame(animId);
  }, [isListening, isSpeaking]);

  const strokeColor = (isListening || isSpeaking) ? '#ff9e00' : (state === 'THINKING' ? '#a78bfa' : '#00d4ff');

  return (
    <div className="absolute -bottom-14 flex items-center justify-center w-[320px] h-[40px] pointer-events-none opacity-80">
      <svg width="320" height="40" className="overflow-visible">
        <path 
          ref={pathRef1} 
          fill="none" 
          stroke={strokeColor} 
          strokeWidth="1.5"
          className="transition-colors duration-500"
        />
        <path 
          ref={pathRef2} 
          fill="none" 
          stroke={strokeColor} 
          strokeWidth="1"
          strokeDasharray="2 3"
          className="opacity-55 transition-colors duration-500"
        />
      </svg>
    </div>
  );
}

// ============================================================================
// 3. SENTRIORB COMPONENT
// ============================================================================
function SentriOrb({ state = "IDLE", scale = 1 }) {
  const isStandby = state === "STANDBY";
  const isWaking = state === "WAKING";
  const isWorkbench = state === "WORKBENCH";
  const isMind = state === "MIND";
  const isBuild = state === "BUILD" || state === "OPEN SOURCE";
  const isListening = state === "LISTENING";
  const isSpeaking = state === "SPEAKING";
  const isThinking = state === "THINKING" || isWorkbench || isMind;
  const isLowPower = isStandby;

  // Theme values (static orb colors)
  const cyanStroke = isStandby ? "#4b5563" : "#00e5ff";
  const orangeStroke = isStandby ? "#4b5563" : "#ff9e00";
  const cyanText = isStandby ? "#4b5563" : "#00e5ff";
  
  // Dynamic status word color mapping
  const subText = isStandby 
    ? "#ef4444" 
    : (isWaking ? "#00e5ff" : isWorkbench ? "#F7C65C" : isMind ? "#a78bfa" : (isListening || isSpeaking ? "#ff9e00" : isBuild ? "#C14DFF" : "#71ebff"));

  // Animation classes
  const cwClass = isLowPower ? "" : "rotate-cw";
  const ccwClass = isLowPower ? "" : "rotate-ccw";
  const pulseClass = isLowPower ? "" : "pulse-slow";

  return (
    <div 
      className="relative w-[320px] h-[160px] md:w-[800px] md:h-[400px] flex items-center justify-center select-none transition-all duration-700 ease-out"
      style={{ transform: `scale(${scale})` }}
    >
      <style>
        {`
          @keyframes rotateCw {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
          }
          @keyframes rotateCcw {
            from { transform: rotate(360deg); }
            to { transform: rotate(-360deg); }
          }
          @keyframes pulseSlow {
            0%, 100% { opacity: 0.6; }
            50% { opacity: 1; }
          }
          .rotate-cw {
            transform-origin: 400px 200px;
            animation: rotateCw 25s linear infinite;
          }
          .rotate-ccw {
            transform-origin: 400px 200px;
            animation: rotateCcw 20s linear infinite;
          }
          .pulse-slow {
            animation: pulseSlow 3s ease-in-out infinite;
          }
        `}
      </style>

      <svg
        width="100%"
        height="100%"
        viewBox="0 0 800 400"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="overflow-visible"
      >
        <defs>
          <filter id="glow-orange" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-cyan" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Central Orb Circle Body & Text */}
        <g>
          <circle cx="400" cy="200" r="72" fill="#000000" fillOpacity="0.8" stroke={cyanStroke} strokeWidth="1.5" strokeOpacity="0.9" />

          {/* Inward Ticks / Crosshairs */}
          <line x1="400" y1="128" x2="400" y2="136" stroke={cyanStroke} strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1="400" y1="272" x2="400" y2="264" stroke={cyanStroke} strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1="328" y1="200" x2="336" y2="200" stroke={cyanStroke} strokeWidth="1.5" strokeOpacity="0.8" />
          <line x1="472" y1="200" x2="464" y2="200" stroke={cyanStroke} strokeWidth="1.5" strokeOpacity="0.8" />

          {/* Content text */}
          <text x="400" y="193" textAnchor="middle" fill={cyanText} className="font-mono font-bold tracking-[0.25em] text-[18px]">SENTRI</text>
          <text x="400" y="211" textAnchor="middle" fill={subText} className="font-mono font-bold tracking-[0.2em] text-[10px] uppercase opacity-95">{state}</text>
        </g>

        {/* Inner Dial with Fine Ticks */}
        <circle
          cx="400"
          cy="200"
          r="82"
          fill="none"
          stroke={cyanStroke}
          strokeWidth="3.5"
          strokeOpacity="0.35"
          strokeDasharray="1.5 2.5"
          className={cwClass}
        />

        {/* Text Path Arc */}
        <g>
          <path id="hud-text-path-1" d="M 312 182 A 92 92 0 0 1 488 182" fill="none" />
          <text fill={cyanText} fontSize="7.5" fontFamily="monospace" letterSpacing="2px" opacity="0.75" className="font-bold">
            <textPath href="#hud-text-path-1" startOffset="5%">
              {isStandby ? "// STANDBY_MODE // POWER_SAVING" : "// SYSTEM_OK // SENTRI_ACTIVE"}
            </textPath>
          </text>
        </g>

        {/* Concentric Ticked Ring 2 */}
        <circle
          cx="400"
          cy="200"
          r="98"
          fill="none"
          stroke={cyanStroke}
          strokeWidth="2"
          strokeOpacity="0.2"
          strokeDasharray="1 4.5"
          className={ccwClass}
        />

        {/* Concentric Double Boundaries */}
        <circle cx="400" cy="200" r="106" fill="none" stroke={orangeStroke} strokeWidth="0.5" strokeOpacity="0.2" />
        <circle cx="400" cy="200" r="118" fill="none" stroke={orangeStroke} strokeWidth="0.5" strokeOpacity="0.2" />

        {/* Four Glowing Brackets */}
        <g className={pulseClass}>
          <path d="M 294.8 161.7 A 112 112 0 0 1 361.7 94.8" stroke={orangeStroke} strokeWidth="3" fill="none" strokeLinecap="round" filter={isStandby ? "" : "url(#glow-orange)"} />
          <path d="M 438.3 94.8 A 112 112 0 0 1 505.2 161.7" stroke={orangeStroke} strokeWidth="3" fill="none" strokeLinecap="round" filter={isStandby ? "" : "url(#glow-orange)"} />
          <path d="M 505.2 238.3 A 112 112 0 0 1 438.3 305.2" stroke={orangeStroke} strokeWidth="3" fill="none" strokeLinecap="round" filter={isStandby ? "" : "url(#glow-orange)"} />
          <path d="M 361.7 305.2 A 112 112 0 0 1 294.8 238.3" stroke={orangeStroke} strokeWidth="3" fill="none" strokeLinecap="round" filter={isStandby ? "" : "url(#glow-orange)"} />
        </g>

        {/* Outer Concentric Cyan Rings */}
        <circle cx="400" cy="200" r="128" fill="none" stroke={cyanStroke} strokeWidth="1" strokeOpacity="0.35" />

        <circle
          cx="400"
          cy="200"
          r="136"
          fill="none"
          stroke={cyanStroke}
          strokeWidth="3.5"
          strokeOpacity={isStandby ? 0.2 : 0.8}
          strokeDasharray="90 50 140 60 70 40"
          filter={isStandby ? "" : "url(#glow-cyan)"}
          className={ccwClass}
        />

        <circle cx="400" cy="200" r="146" fill="none" stroke={cyanStroke} strokeWidth="1" strokeOpacity="0.4" />
        <circle
          cx="400"
          cy="200"
          r="149"
          fill="none"
          stroke={cyanStroke}
          strokeWidth="6"
          strokeOpacity="0.3"
          strokeDasharray="1.5 5.5"
          className={cwClass}
        />
      </svg>

      {/* AUDIO WAVEFORM */}
      {!isStandby && <AudioWaveform state={state} />}
    </div>
  );
}

// ============================================================================
// DATA SOURCES (Vision Document Mappings)
// ============================================================================
const JOURNAL_LOGS = [
  { date: "July 12, 2026", title: "Speech Pipeline Calibration", text: "Successfully integrated Kokoro TTS with Faster-Whisper ASR. Runs entirely in local WebAssembly shaders. WebSocket response latency below 120ms." },
  { date: "July 05, 2026", title: "Memory Relational Constellation", text: "Calibrated on-device SQLite preference daemon. Extracted facts and preferences persist locally without central synchronization." },
  { date: "June 28, 2026", title: "Reasoning Core Optimization", text: "Replaced remote cloud endpoints with an unaligned local Qwen model running in CPU/GPU VRAM. Absolute data privacy achieved." },
  { date: "June 15, 2026", title: "Context Leakage Outage Pivot", text: "Telemetry test runs showed remote leakage. Pivoted architecture completely to an offline-first execution model. Technology must disappear." }
];

const WORKBENCH_MODULES = [
  { id: "memory", name: "Memory Engine", icon: "database", desc: "Saves Preferences, stores conversation logs, and maintains context locally via SQLite daemons." },
  { id: "voice", name: "Voice Pipeline", icon: "volume_up", desc: "Pairing Faster-Whisper with Kokoro ONNX. Serves low-latency vocal feedback directly over local WebSockets." },
  { id: "vision", name: "Vision Core", icon: "visibility", desc: "Local canvas frame capture. Recognizes workspace tabs, active windows, and visual layouts natively." },
  { id: "reasoning", name: "Reasoning Matrix", icon: "psychology", desc: "Uncensored Qwen local reasoning cores. Translates intents and coordinates local file edits." },
  { id: "planning", name: "Task Planning", icon: "assignment", desc: "Iterative goal planner. Translates user commands into sequential checklists and monitors output." },
  { id: "tools", name: "Native Tools", icon: "construction", desc: "Local OS terminal connectors. Runs PowerShell scripts, edits files, and queries directories." },
  { id: "open_source", name: "Open Source", icon: "lock_open", desc: "Zero unlicensed binaries. Everything is buildable, auditable, and customizable by the community." }
];

const GIT_COMMITS = [
  "commit 8f92cd3 - feat: Kokoro voice speech web sockets integration (12h ago)",
  "commit a3c01ff - fix: local SQLite daemon memory leak resolved (1d ago)",
  "commit e8249bb - docs: update local workspace dev instruction manual (2d ago)",
  "commit c0181ef - refactor: remove all telemetry endpoints for total privacy (3d ago)"
];

// ============================================================================
// 4. MAIN APPLICATION
// ============================================================================
function App() {
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState(0);
  const [scrollY, setScrollY] = useState(0);
  const [orbState, setOrbState] = useState('STANDBY');
  const [orbScale, setOrbScale] = useState(1.1);
  const [orbPosition, setOrbPosition] = useState({ x: 0, y: 0 });

  const [activeModule, setActiveModule] = useState(null);
  const [chatInput, setChatInput] = useState("");
  const [chatOutput, setChatOutput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  const canvasRef = useRef(null);

  // Preloader progress simulator
  useEffect(() => {
    if (progress < 100) {
      const timer = setTimeout(() => setProgress(p => p + 2), 20 + Math.random() * 30);
      return () => clearTimeout(timer);
    } else {
      setTimeout(() => setLoading(false), 600);
    }
  }, [progress]);

  // Track scroll position to update orb positions & states dynamically
  useEffect(() => {
    const handleScroll = () => {
      const currentScroll = window.scrollY;
      setScrollY(currentScroll);

      const sec2 = document.getElementById('sec-journal');
      const sec3 = document.getElementById('sec-workbench');
      const sec4 = document.getElementById('sec-mind');
      const sec5 = document.getElementById('sec-conversation');
      const sec6 = document.getElementById('sec-footer');

      const t2 = sec2 ? sec2.offsetTop : window.innerHeight * 0.8;
      const t3 = sec3 ? sec3.offsetTop : window.innerHeight * 1.6;
      const t4 = sec4 ? sec4.offsetTop : window.innerHeight * 2.4;
      const t5 = sec5 ? sec5.offsetTop : window.innerHeight * 3.2;
      const t6 = sec6 ? sec6.offsetTop : window.innerHeight * 4.0;

      const isDesktop = window.innerWidth > 768;

      if (currentScroll < t2 * 0.5) {
        setOrbState('STANDBY');
        setOrbScale(1.1);
        setOrbPosition({ x: 0, y: 0 });
      } else if (currentScroll >= t2 * 0.5 && currentScroll < (t2 + t3) / 2) {
        setOrbState('WAKING');
        setOrbScale(0.85);
        setOrbPosition({ x: isDesktop ? 250 : 0, y: 0 });
      } else if (currentScroll >= (t2 + t3) / 2 && currentScroll < (t3 + t4) / 2) {
        setOrbState('WORKBENCH');
        setOrbScale(0.75);
        setOrbPosition({ x: isDesktop ? -250 : 0, y: 0 });
      } else if (currentScroll >= (t3 + t4) / 2 && currentScroll < (t4 + t5) / 2) {
        setOrbState('MIND');
        setOrbScale(0.9);
        setOrbPosition({ x: 0, y: 0 });
      } else if (currentScroll >= (t4 + t5) / 2 && currentScroll < (t5 + t6) / 2) {
        setOrbState('LISTENING');
        setOrbScale(0.85);
        setOrbPosition({ x: isDesktop ? 250 : 0, y: 0 });
      } else {
        setOrbState('BUILD');
        setOrbScale(1.2);
        setOrbPosition({ x: 0, y: -80 });
      }
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleSendChat = (e) => {
    e.preventDefault();
    if (!chatInput.trim() || isTyping) return;

    setIsTyping(true);
    setChatOutput("");
    const userMsg = chatInput;
    setChatInput("");

    // Simulate S.E.N.T.R.I response typing
    const responses = [
      "I am aligned. Secure offline context verified. How shall we proceed with calibration?",
      "Workspace directory verified. All native connectors are active and standing by.",
      "Relational memory updated. Relational databases are offline-first and fully protected.",
      "Kokoro voice frequencies calibrated. Audio websockets ready for dialogue."
    ];
    const responseText = responses[Math.floor(Math.random() * responses.length)];
    let currentIdx = 0;
    
    // Set orb state to SPEAKING during reply
    setOrbState('SPEAKING');

    const interval = setInterval(() => {
      setChatOutput(prev => prev + responseText[currentIdx]);
      currentIdx++;
      if (currentIdx >= responseText.length) {
        clearInterval(interval);
        setIsTyping(false);
        setOrbState('LISTENING');
      }
    }, 25);
  };

  // Three.js swirling background particles & grid parallax scene
  useEffect(() => {
    if (loading) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    let w = window.innerWidth;
    let h = window.innerHeight;

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x030508, 0.015); // Smoothly fades grids into black void at the horizon

    const camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
    camera.position.z = 12;

    // 1. Perspective Grid Helpers (Infinite Floor & Ceiling grids)
    const gridColorHex = 0x00d4ff;
    const floorGrid = new THREE.GridHelper(2000, 1000, gridColorHex, gridColorHex);
    floorGrid.position.y = -6.5;
    floorGrid.material.opacity = 0.14;
    floorGrid.material.transparent = true;
    scene.add(floorGrid);

    const ceilingGrid = new THREE.GridHelper(2000, 1000, gridColorHex, gridColorHex);
    ceilingGrid.position.y = 6.5;
    ceilingGrid.material.opacity = 0.08;
    ceilingGrid.material.transparent = true;
    scene.add(ceilingGrid);

    // 2. Swirling tunnel particles
    const PARTICLE_COUNT = 900;
    const geometry = new THREE.BufferGeometry();
    const positions = new Float32Array(PARTICLE_COUNT * 3);

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = (i / PARTICLE_COUNT) * Math.PI * 25;
      const radius = 3.5 + Math.random() * 2.5;
      const x = Math.cos(angle) * radius;
      const y = (Math.random() - 0.5) * 18;
      const z = Math.sin(angle) * radius;

      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
    }

    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));

    const material = new THREE.PointsMaterial({
      color: 0x00d4ff,
      size: 0.055,
      sizeAttenuation: true,
      transparent: true,
      opacity: 0.55
    });

    const particleSystem = new THREE.Points(geometry, material);
    scene.add(particleSystem);

    let animId;
    const clock = new THREE.Clock();

    // Scroll speed calculators for Z-warp drive effect
    let targetScrollY = window.scrollY;
    let currentScrollY = window.scrollY;
    let scrollSpeed = 0;

    const handleScrollEvent = () => {
      targetScrollY = window.scrollY;
    };
    window.addEventListener('scroll', handleScrollEvent);

    const animate = () => {
      animId = requestAnimationFrame(animate);
      const elapsed = clock.getElapsedTime();

      // Smoothly interpolate scroll Y to calculate scroll velocity/speed
      const diff = targetScrollY - currentScrollY;
      currentScrollY += diff * 0.06;
      scrollSpeed = Math.abs(diff) * 0.09;

      particleSystem.rotation.y = elapsed * 0.035;
      particleSystem.rotation.x = Math.sin(elapsed * 0.1) * 0.05;
      
      // Rotate grid helpers slightly to give deep motion
      floorGrid.rotation.y = -elapsed * 0.01;
      ceilingGrid.rotation.y = elapsed * 0.01;

      // Scroll z-camera movement
      const scrollRatio = currentScrollY / document.documentElement.scrollHeight;
      camera.position.z = 12 - scrollRatio * 8;
      camera.position.y = -scrollRatio * 6;

      // WORMHOLE WARP DRIVE: scale Z scale and stretch camera FOV based on scroll speed
      particleSystem.scale.z = 1.0 + Math.min(scrollSpeed * 0.22, 6.0);
      camera.fov = 45 + Math.min(scrollSpeed * 0.45, 25.0);
      camera.updateProjectionMatrix();

      // Background lighting color transitions depending on scroll offset
      let targetColor = new THREE.Color(0x00d4ff); // standby/waking cyan
      let gridColor = new THREE.Color(0x00d4ff);

      if (currentScrollY > window.innerHeight * 0.5) {
        targetColor = new THREE.Color(0x7c3aed); // violet thinking
        gridColor = new THREE.Color(0x7c3aed);
      }
      if (currentScrollY > window.innerHeight * 1.5) {
        targetColor = new THREE.Color(0xff9e00); // orange speaking
        gridColor = new THREE.Color(0xff9e00);
      }

      material.color.lerp(targetColor, 0.04);
      floorGrid.material.color.lerp(gridColor, 0.04);
      ceilingGrid.material.color.lerp(gridColor, 0.04);

      renderer.render(scene, camera);
    };

    animate();

    const handleResize = () => {
      w = window.innerWidth;
      h = window.innerHeight;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('scroll', handleScrollEvent);
      window.removeEventListener('resize', handleResize);
      cancelAnimationFrame(animId);
      scene.remove(particleSystem);
      scene.remove(floorGrid);
      scene.remove(ceilingGrid);
      geometry.dispose();
      material.dispose();
    };
  }, [loading]);

  return (
    <div className="relative bg-[#030508] text-slate-100 min-h-screen select-none font-sans overflow-x-hidden">
      
      {/* CINEMATIC PRELOADER */}
      {loading && (
        <div className="fixed inset-0 bg-[#05070a] z-[9999] flex flex-col items-center justify-center font-mono">
          <div className="flex flex-col items-center gap-4">
            <div className="text-[10px] text-primary/60 tracking-[0.3em] uppercase animate-pulse">BOOTING INTEGRITY ENGINE</div>
            <div className="text-5xl md:text-8xl font-bold tracking-tighter text-white glow-text">
              {String(progress).padStart(3, '0')}%
            </div>
            <div className="w-[180px] h-[1px] bg-slate-800 relative overflow-hidden mt-2">
              <div 
                className="h-full bg-primary shadow-[0_0_8px_#00d4ff] transition-all duration-100"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        </div>
      )}

      <div className="crt-overlay"></div>
      <div className="vignette"></div>

      {/* 3D WebGL Background Canvas */}
      {!loading && (
        <div className="fixed inset-0 z-0 w-full h-full pointer-events-none">
          <canvas ref={canvasRef} className="w-full h-full absolute inset-0"></canvas>
        </div>
      )}

      {/* Backdrop Ambient Lighting */}
      <div className="fixed top-[-10%] left-[20%] w-[60%] h-[60%] bg-gradient-to-b from-[#00d4ff]/10 via-[#7c3aed]/5 to-transparent rounded-full filter blur-[150px] pointer-events-none z-0"></div>

      {/* HEADER */}
      <header className="fixed top-0 left-0 w-full z-50 h-20 flex items-center justify-between px-8 md:px-16 pointer-events-none">
        <div className="flex items-center gap-3 pointer-events-auto">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_#00d4ff]"></span>
          <span className="font-mono text-xs font-bold tracking-[0.25em] text-white">S.E.N.T.R.I.</span>
        </div>
        <div className="font-mono text-[9px] tracking-widest text-primary border border-primary/30 bg-primary/5 px-4 py-1.5 rounded-full pointer-events-auto">
          <ScrambleText text="LAUNCH ALPHA" />
        </div>
      </header>

      {/* FIXED DYNAMIC 2D ORB CONTAINER */}
      {!loading && (
        <div 
          className="fixed inset-0 z-10 flex items-center justify-center pointer-events-none transition-all duration-700 ease-out"
          style={{ 
            transform: `translate(${orbPosition.x}px, ${orbPosition.y}px)` 
          }}
        >
          <SentriOrb state={orbState} scale={orbScale} />
        </div>
      )}

      {/* SCROLL JOURNEY SECTIONS */}
      {!loading && (
        <div className="relative z-20 w-full">
          
          {/* SECTION 1: HERO VIEW */}
          <section id="sec-hero" className="h-screen w-full flex flex-col justify-between items-center px-6 py-20 relative">
            <div></div>
            <div className="text-center flex flex-col items-center max-w-4xl gap-6">
              <h1 className="font-mono text-5xl md:text-7xl font-bold tracking-[0.4em] text-white glow-text uppercase leading-none select-none pl-7">
                S.E.N.T.R.I
              </h1>
              <p className="font-mono text-xs md:text-sm tracking-[0.18em] text-slate-300 max-w-xl leading-relaxed uppercase">
                Someone Everyone Needs To Remember
              </p>
            </div>
            
            <div className="flex flex-col items-center gap-2 font-mono text-[9px] text-primary/60 animate-bounce">
              <span>SCROLL TO AWAKEN</span>
              <span className="material-symbols-outlined text-sm">keyboard_double_arrow_down</span>
            </div>
          </section>

          {/* SECTION 2: RESEARCH JOURNAL */}
          <section id="sec-journal" className="min-h-[70vh] py-20 w-full flex items-center px-8 md:px-24">
            <div className="w-full max-w-lg flex flex-col gap-6">
              <ScrambleInHeader text="// ROOM 01 // RESEARCH JOURNAL" className="font-mono text-xs text-[#00e5ff] font-bold tracking-[0.2em]" />
              <ScrambleInHeader 
                text="LOGGING PROGRESS AND LESSONS." 
                className="text-3xl md:text-5xl font-mono font-bold tracking-tight text-white uppercase block" 
              />
              <div className="flex flex-col gap-6 mt-6">
                {JOURNAL_LOGS.map((log, index) => (
                  <div key={index} className="journal-log flex flex-col gap-1">
                    <span className="journal-dot"></span>
                    <span className="font-mono text-[10px] text-slate-500 tracking-wider uppercase">{log.date}</span>
                    <h3 className="font-mono text-xs font-bold text-white uppercase">{log.title}</h3>
                    <p className="text-xs text-slate-300 leading-relaxed max-w-md">{log.text}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* SECTION 3: THE WORKBENCH */}
          <section id="sec-workbench" className="min-h-[70vh] py-20 w-full flex items-center justify-end px-8 md:px-24">
            <div className="w-full max-w-2xl flex flex-col gap-6 text-right items-end">
              <ScrambleInHeader text="// ROOM 02 // THE WORKBENCH" className="font-mono text-xs text-[#F7C65C] font-bold tracking-[0.2em]" />
              <ScrambleInHeader 
                text="INTERACTIVE SYSTEM MODULES." 
                className="text-3xl md:text-5xl font-mono font-bold tracking-tight text-white uppercase block" 
              />
              <p className="text-sm text-slate-300 max-w-md leading-relaxed">
                S.E.N.T.R.I. is composed of highly decoupled, modular local engines. Click on any module below to inspect its details on the workbench.
              </p>
              
              {/* Workbench Modules Grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 w-full mt-6 text-left">
                {WORKBENCH_MODULES.map((mod) => (
                  <div 
                    key={mod.id} 
                    onClick={() => setActiveModule(activeModule === mod.id ? null : mod.id)}
                    className={`workbench-card p-4 rounded cursor-pointer border ${activeModule === mod.id ? 'active border-[#F7C65C]' : 'border-slate-800'}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="material-symbols-outlined text-md" style={{ color: activeModule === mod.id ? '#F7C65C' : '#BEBEBE' }}>
                        {mod.icon}
                      </span>
                      <span className="font-mono text-[9px] text-slate-500 tracking-wider">
                        {activeModule === mod.id ? 'ACTIVE' : 'INSPECT'}
                      </span>
                    </div>
                    <h4 className="font-mono text-xs font-bold text-white uppercase">{mod.name}</h4>
                  </div>
                ))}
              </div>

              {/* Expanded Module Details */}
              {activeModule && (
                <div className="w-full text-left p-6 mt-4 border border-[#F7C65C]/30 bg-[#111111]/85 backdrop-blur rounded bracket-corners">
                  <div className="br-tr"></div><div className="br-bl"></div>
                  <h5 className="font-mono text-xs font-bold text-[#F7C65C] uppercase tracking-wider mb-2">
                    // MODULE CONFIGURATION: {WORKBENCH_MODULES.find(m => m.id === activeModule)?.name}
                  </h5>
                  <p className="text-xs text-slate-300 leading-relaxed max-w-xl">
                    {WORKBENCH_MODULES.find(m => m.id === activeModule)?.desc}
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* SECTION 4: THE MIND */}
          <section id="sec-mind" className="min-h-[70vh] py-20 w-full flex items-center px-8 md:px-24">
            <div className="w-full max-w-lg flex flex-col gap-6">
              <ScrambleInHeader text="// ROOM 03 // THE MIND" className="font-mono text-xs text-[#a78bfa] font-bold tracking-[0.2em]" />
              <ScrambleInHeader 
                text="A LIVING VISUALIZATION." 
                className="text-3xl md:text-5xl font-mono font-bold tracking-tight text-white uppercase block" 
              />
              <p className="text-sm md:text-base text-slate-300 leading-relaxed">
                Sentri's intelligence flows in slow, branching networks. Decisions branch, memories reinforce, and logic paths connect organically. Every interaction calibrates her core, shaping her digital consciousness.
              </p>
              <div className="flex items-center gap-6 mt-4">
                <div className="font-mono text-[10px] text-slate-400 border border-slate-700/60 px-4 py-2 rounded bg-slate-900/40">
                  LOGIC: DIRECTED_GRAPH
                </div>
                <div className="font-mono text-[10px] text-slate-400 border border-slate-700/60 px-4 py-2 rounded bg-slate-900/40">
                  FOG_DENSITY: 0.015
                </div>
              </div>
            </div>
          </section>

          {/* SECTION 5: CONVERSATION */}
          <section id="sec-conversation" className="min-h-[70vh] py-20 w-full flex items-center justify-end px-8 md:px-24">
            <div className="w-full max-w-lg flex flex-col gap-6 text-right items-end">
              <ScrambleInHeader text="// ROOM 04 // CONVERSATION" className="font-mono text-xs text-[#6CE5A2] font-bold tracking-[0.2em]" />
              <ScrambleInHeader 
                text="PEACEFUL CONVERSATION SURFACE." 
                className="text-3xl md:text-5xl font-mono font-bold tracking-tight text-white uppercase block" 
              />
              <p className="text-sm text-slate-300 leading-relaxed max-w-md">
                Engage with Sentri directly. The interface disappears, leaving only dialogue. Talk, ask questions, or run tasks.
              </p>

              {/* Minimal Chat Form */}
              <form onSubmit={handleSendChat} className="w-full mt-4 flex flex-col gap-3 items-end">
                <div className="w-full relative">
                  <input
                    type="text"
                    value={chatInput}
                    onChange={(e) => setChatInput(e.target.value)}
                    placeholder="Type your message to converse..."
                    className="w-full bg-[#111111]/70 border border-slate-800 focus:border-[#6CE5A2] focus:outline-none px-6 py-4 rounded text-xs font-mono text-white placeholder-slate-500 transition-all duration-300"
                    disabled={isTyping}
                  />
                  {isTyping && (
                    <span className="absolute right-6 top-1/2 transform -translate-y-1/2 font-mono text-[9px] text-[#6CE5A2] animate-pulse">
                      TYPING...
                    </span>
                  )}
                </div>
                <button 
                  type="submit" 
                  disabled={isTyping || !chatInput.trim()}
                  className="hud-panel px-6 py-2.5 rounded font-mono text-[10px] tracking-wider text-[#6CE5A2] border border-[#6CE5A2]/30 hover:bg-[#6CE5A2]/10 transition-all duration-300 disabled:opacity-40 disabled:hover:bg-transparent"
                >
                  SEND MESSAGE
                </button>
              </form>

              {/* Chat Output response */}
              {chatOutput && (
                <div className="w-full text-left p-6 mt-4 border border-[#6CE5A2]/30 bg-[#111111]/85 backdrop-blur rounded font-mono text-xs text-slate-300 leading-relaxed">
                  <span className="text-[#6CE5A2] font-bold block mb-1">SENTRI:</span>
                  {chatOutput}
                </div>
              )}
            </div>
          </section>

          {/* SECTION 6: BUILD & OPEN SOURCE */}
          <section id="sec-footer" className="min-h-screen w-full flex flex-col justify-between items-center px-6 pt-24 pb-12 relative bg-gradient-to-t from-[#05070a] to-transparent">
            <div className="w-full max-w-4xl flex flex-col items-center gap-8 z-30 text-center">
              <ScrambleInHeader text="// ROOM 05 // BUILD & OPEN SOURCE" className="font-mono text-xs text-[#C14DFF] font-bold tracking-[0.2em]" />
              <h2 className="font-mono text-4xl md:text-6xl font-bold tracking-tighter text-white">
                CELEBRATE SOURCE TRANSPARENCY
              </h2>
              <p className="text-xs md:text-sm text-slate-400 max-w-lg leading-relaxed">
                Everything is open. S.E.N.T.R.I. belongs to the community. Run commits, audit logic paths, or contribute to Kokoro voice pipelines.
              </p>

              {/* Git Transparency Terminal Dashboard */}
              <div className="w-full max-w-2xl text-left git-terminal overflow-hidden mt-4">
                <div className="git-terminal-header px-4 py-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full bg-red-500/80"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-yellow-500/80"></span>
                    <span className="w-2.5 h-2.5 rounded-full bg-green-500/80"></span>
                  </div>
                  <span className="font-mono text-[9px] text-[#C14DFF] tracking-wider uppercase font-bold">// GIT_TRANSPARENCY_BOARD</span>
                </div>
                <div className="p-4 flex flex-col gap-3 font-mono text-[10px] text-slate-300">
                  <div className="flex items-center gap-2 text-green-400">
                    <span className="material-symbols-outlined text-xs">check_circle</span>
                    <span>BUILD INTEGRITY: PASSING (V2.0.4-LTS)</span>
                  </div>
                  <div className="flex flex-col gap-2.5 mt-2 border-t border-slate-900 pt-3">
                    <span className="text-slate-500 uppercase">// LATEST VERIFIED COMMITS:</span>
                    {GIT_COMMITS.map((commit, idx) => (
                      <div key={idx} className="git-log-line font-mono text-slate-400">
                        {commit}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              <div className="flex flex-col md:flex-row items-center gap-4 mt-6">
                <a
                  href="https://github.com/NeuralNinja23/S.E.N.T.R.I"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hud-panel px-8 py-3.5 rounded-full font-mono text-[10px] tracking-widest text-[#C14DFF] border border-[#C14DFF]/40 hover:bg-[#C14DFF]/10 transition-all duration-300 focus:outline-none"
                >
                  VIEW GITHUB SOURCE
                </a>
                <a
                  href="https://github.com/NeuralNinja23/S.E.N.T.R.I/tree/sentri-v2"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hud-panel px-8 py-3.5 rounded-full font-mono text-[10px] tracking-widest text-white border border-white/20 hover:bg-white/5 transition-all duration-300 focus:outline-none"
                >
                  DOWNLOAD STABLE RELEASES
                </a>
              </div>
            </div>

            <footer className="w-full flex items-center justify-center pt-16 font-mono text-[10px] text-slate-600">
              <span> © 2026 S.E.N.T.R.I — Digital Human. Developed by NeuralNinja23</span>
            </footer>
          </section>

        </div>
      )}

    </div>
  );
}

export default App;
