import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";

export function createKitchenScene(container) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#eef1ed");

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.12;
  renderer.domElement.style.cssText =
    "display:block;width:100%;height:100%;touch-action:none;";
  renderer.domElement.setAttribute("role", "img");
  container.appendChild(renderer.domElement);

  const camera = new THREE.OrthographicCamera(-6, 6, 3.7, -3.7, 0.1, 80);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.enablePan = false;
  controls.minPolarAngle = Math.PI / 6;
  controls.maxPolarAngle = Math.PI / 2.5;
  controls.minAzimuthAngle = -0.15;
  controls.maxAzimuthAngle = Math.PI / 2.1;
  controls.minZoom = 0.75;
  controls.maxZoom = 1.8;
  controls.rotateSpeed = 0.65;

  const room = new THREE.Group();
  scene.add(room);

  const mat = (color, options = {}) =>
    new THREE.MeshStandardMaterial({ color, roughness: 0.78, ...options });
  const palette = {
    plaster: mat("#e4e7dc"),
    wallEdge: mat("#d2d9cc"),
    ivory: mat("#fff7e5"),
    white: mat("#fffdf4", { roughness: 0.5 }),
    sage: mat("#839d8e"),
    sageDark: mat("#637e6e"),
    sageLight: mat("#9db3a2"),
    wood: mat("#c29461"),
    woodEdge: mat("#a97847"),
    woodGrain: mat("#b88b59"),
    dark: mat("#35413c"),
    rubber: mat("#333d3a"),
    brass: mat("#b99557", { roughness: 0.35, metalness: 0.65 }),
    metal: mat("#afbbb5", { roughness: 0.3, metalness: 0.65 }),
    terracotta: mat("#c17e5d"),
    green: mat("#527b50"),
    leaf: mat("#72935c"),
    tile: mat("#e9e4d7"),
    tileAlt: mat("#e0ded0"),
    grout: mat("#cecfc1"),
    accent: mat("#358f7e", {
      roughness: 0.38,
      emissive: "#358f7e",
      emissiveIntensity: 0.18,
    }),
    visor: mat("#264c47", { roughness: 0.24, metalness: 0.18 }),
    eye: mat("#9df2d6", { emissive: "#7fe6c3", emissiveIntensity: 1.2 }),
    cloth: mat("#e8ede0"),
    glass: mat("#d3e1d8", {
      transparent: true,
      opacity: 0.45,
      roughness: 0.16,
      metalness: 0.1,
    }),
    ovenGlass: mat("#29332f", {
      transparent: true,
      opacity: 0.48,
      roughness: 0.28,
    }),
    window: mat("#c2d9d0", { emissive: "#c8e6de", emissiveIntensity: 0.18 }),
    bulb: mat("#ffe2a0", { emissive: "#ffdf99", emissiveIntensity: 0.7 }),
  };

  function mesh(geometry, material, x, y, z, parent = room) {
    const object = new THREE.Mesh(geometry, material);
    object.position.set(x, y, z);
    object.castShadow = true;
    object.receiveShadow = true;
    parent.add(object);
    return object;
  }

  function box(w, h, d, material, x, y, z, parent = room, radius = 0) {
    const geometry = radius
      ? new RoundedBoxGeometry(
          w,
          h,
          d,
          2,
          Math.min(radius, w / 2, h / 2, d / 2),
        )
      : new THREE.BoxGeometry(w, h, d);
    return mesh(geometry, material, x, y, z, parent);
  }

  function cylinder(top, bottom, height, material, x, y, z, parent = room) {
    return mesh(
      new THREE.CylinderGeometry(top, bottom, height, 28),
      material,
      x,
      y,
      z,
      parent,
    );
  }

  function sphere(radius, material, x, y, z, parent = room, scale = [1, 1, 1]) {
    const object = mesh(
      new THREE.SphereGeometry(radius, 20, 12),
      material,
      x,
      y,
      z,
      parent,
    );
    object.scale.set(...scale);
    return object;
  }

  function plant(x, y, z, size = 1) {
    const group = new THREE.Group();
    group.position.set(x, y, z);
    group.scale.setScalar(size);
    room.add(group);
    cylinder(0.18, 0.13, 0.3, palette.terracotta, 0, 0.15, 0, group);
    cylinder(0.163, 0.163, 0.02, palette.woodEdge, 0, 0.305, 0, group);
    cylinder(0.014, 0.02, 0.63, palette.green, 0, 0.59, 0, group);
    for (let i = 0; i < 7; i++) {
      const angle = i * 2.4;
      const leaf = sphere(
        0.15,
        i % 2 ? palette.green : palette.leaf,
        Math.cos(angle) * 0.13,
        0.43 + i * 0.07,
        Math.sin(angle) * 0.13,
        group,
        [0.62, 1.4, 0.27],
      );
      leaf.rotation.set(Math.cos(angle) * 0.75, -angle, Math.sin(angle) * 0.75);
    }
    return group;
  }

  // The raised tile base and two open walls keep the kitchen legible at demo scale.
  box(8.9, 0.3, 6.8, palette.wallEdge, 0, -0.2, 0, room, 0.09);
  box(8.7, 0.06, 6.6, palette.grout, 0, -0.025, 0);
  for (let x = 0; x < 11; x++) {
    for (let z = 0; z < 8; z++) {
      box(
        0.777,
        0.025,
        0.802,
        (x + z) % 2 ? palette.tileAlt : palette.tile,
        -3.965 + x * 0.793,
        0.019,
        -2.85 + z * 0.82,
      );
    }
  }
  box(8.8, 3.0, 0.16, palette.plaster, 0, 1.5, -3.3, room, 0.025);
  box(0.16, 3.0, 4.45, palette.plaster, -4.35, 1.5, -1.14, room, 0.025);
  box(8.62, 0.12, 0.05, palette.ivory, 0, 0.11, -3.18);
  box(0.05, 0.12, 4.43, palette.ivory, -4.24, 0.11, -1.13);
  const ground = mesh(
    new THREE.PlaneGeometry(200, 200),
    mat("#eef1ed"),
    0,
    -0.365,
    0,
    scene,
  );
  ground.rotation.x = -Math.PI / 2;
  ground.castShadow = false;

  // Cabinets, a continuous oak worktop, and a tiled backsplash.
  box(1.5, 0.91, 1.12, palette.sageDark, -1.8, 0.52, -2.62, room, 0.035);
  box(3.73, 0.91, 1.12, palette.sageDark, 2.015, 0.52, -2.62, room, 0.035);
  box(6.62, 0.14, 1.28, palette.wood, 0.65, 1.05, -2.58, room, 0.045);
  for (const x of [-2.1, -1.37, 0.43, 1.25, 2.1, 2.95, 3.65]) {
    const width = x === 3.65 ? 0.48 : 0.72;
    box(width, 0.77, 0.055, palette.sage, x, 0.54, -2.03, room, 0.025);
    box(
      width - 0.12,
      0.59,
      0.018,
      palette.sageLight,
      x,
      0.54,
      -1.995,
      room,
      0.012,
    );
    box(0.21, 0.035, 0.042, palette.brass, x, 0.79, -1.97, room, 0.013);
  }
  for (let row = 0; row < 3; row++) {
    for (let col = 0; col < 12; col++) {
      box(
        0.515,
        0.19,
        0.025,
        palette.ivory,
        -2.22 + col * 0.537,
        1.25 + row * 0.215,
        -3.185,
      );
    }
  }

  // Refrigerator with a small pinned note and its characteristic long handles.
  box(1.31, 2.55, 1.3, palette.ivory, -3.43, 1.33, -2.53, room, 0.09);
  box(1.23, 1.56, 0.06, palette.white, -3.43, 1.78, -1.852, room, 0.055);
  box(1.23, 0.78, 0.06, palette.white, -3.43, 0.54, -1.852, room, 0.055);
  box(0.055, 0.68, 0.06, palette.brass, -2.99, 1.56, -1.788, room, 0.025);
  box(0.055, 0.4, 0.06, palette.brass, -2.99, 0.56, -1.788, room, 0.025);
  const note = box(0.33, 0.34, 0.014, palette.cloth, -3.58, 1.86, -1.803);
  note.rotation.z = -0.12;
  sphere(0.035, palette.terracotta, -3.56, 2.02, -1.785, room, [1, 1, 0.25]);
  for (let i = 0; i < 3; i++)
    box(
      0.2 - i * 0.025,
      0.012,
      0.005,
      palette.sage,
      -3.58,
      1.92 - i * 0.065,
      -1.791,
    );

  // Oven: its transparent door reveals food and the light follows power state.
  box(1.13, 0.87, 0.06, palette.dark, -0.46, 0.55, -3.11);
  box(0.07, 0.87, 1.18, palette.dark, -0.99, 0.55, -2.55);
  box(0.07, 0.87, 1.18, palette.dark, 0.07, 0.55, -2.55);
  box(1.13, 0.06, 1.18, palette.dark, -0.46, 0.145, -2.55);
  box(1.06, 0.16, 0.065, palette.metal, -0.46, 0.92, -1.928);
  box(0.91, 0.54, 0.028, palette.ovenGlass, -0.46, 0.53, -1.932, room, 0.035);
  box(0.9, 0.048, 0.08, palette.brass, -0.46, 0.78, -1.875, room, 0.018);
  box(0.88, 0.028, 0.88, palette.metal, -0.46, 0.31, -2.49);
  box(0.88, 0.022, 0.88, palette.metal, -0.46, 0.58, -2.49);
  for (const x of [-0.84, -0.66, -0.25, -0.07]) {
    const knob = cylinder(0.043, 0.043, 0.045, palette.dark, x, 0.935, -1.878);
    knob.rotation.x = Math.PI / 2;
  }
  const ovenIndicator = box(
    0.13,
    0.05,
    0.015,
    palette.bulb,
    -0.46,
    0.935,
    -1.886,
  );
  box(1.13, 0.045, 1.02, palette.dark, -0.46, 1.142, -2.56, room, 0.015);
  for (const x of [-0.75, -0.17]) {
    for (const z of [-2.81, -2.29]) {
      cylinder(0.175, 0.175, 0.025, palette.metal, x, 1.175, z);
      cylinder(0.13, 0.13, 0.032, palette.dark, x, 1.188, z);
    }
  }
  const ovenLight = new THREE.PointLight("#ffc16d", 0, 2.2, 2);
  ovenLight.position.set(-0.46, 0.6, -1.9);
  room.add(ovenLight);

  // A broad window, sink, and brass gooseneck tap catch the morning light.
  box(2.75, 1.35, 0.045, palette.woodEdge, 2.05, 2.22, -3.188, room, 0.025);
  box(2.61, 1.22, 0.055, palette.window, 2.05, 2.22, -3.156);
  box(0.055, 1.24, 0.08, palette.ivory, 2.05, 2.22, -3.11);
  box(2.67, 0.05, 0.08, palette.ivory, 2.05, 2.22, -3.11);
  box(2.91, 0.095, 0.28, palette.ivory, 2.05, 1.535, -3.07, room, 0.025);
  box(1.36, 0.035, 0.78, palette.metal, 2.0, 1.13, -2.52, room, 0.08);
  box(1.16, 0.025, 0.6, palette.dark, 2.0, 1.151, -2.5, room, 0.08);
  box(1.05, 0.015, 0.5, palette.glass, 2.0, 1.17, -2.5, room, 0.07);
  const tapCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(2.0, 1.15, -2.94),
    new THREE.Vector3(2.0, 1.58, -2.94),
    new THREE.Vector3(2.0, 1.66, -2.7),
    new THREE.Vector3(2.0, 1.47, -2.57),
  ]);
  mesh(
    new THREE.TubeGeometry(tapCurve, 24, 0.032, 8, false),
    palette.brass,
    0,
    0,
    0,
  );
  cylinder(0.048, 0.048, 0.15, palette.brass, 2.23, 1.2, -2.91);
  plant(3.16, 1.58, -3.06, 0.48);
  plant(3.61, 1.13, -2.64, 0.7);

  // Floating shelf, everyday crockery, and an analog clock.
  box(2.15, 0.09, 0.38, palette.wood, -1.19, 2.05, -3.02, room, 0.02);
  for (const x of [-1.93, -1.5, -0.58]) {
    cylinder(
      0.105,
      0.09,
      0.26,
      x === -0.58 ? palette.terracotta : palette.ivory,
      x,
      2.23,
      -3.0,
    );
    cylinder(0.112, 0.112, 0.04, palette.woodEdge, x, 2.38, -3.0);
  }
  box(0.16, 0.35, 0.24, palette.sageDark, -1.08, 2.27, -3.01);
  box(0.12, 0.3, 0.25, palette.terracotta, -0.92, 2.245, -3.01);
  const clock = new THREE.Group();
  clock.position.set(-1.22, 2.63, -3.135);
  room.add(clock);
  const clockRim = cylinder(0.255, 0.255, 0.065, palette.brass, 0, 0, 0, clock);
  clockRim.rotation.x = Math.PI / 2;
  mesh(new THREE.CircleGeometry(0.229, 48), palette.ivory, 0, 0, 0.038, clock);
  for (let i = 0; i < 12; i++) {
    const angle = (i * Math.PI) / 6;
    const tick = box(
      0.013,
      0.037,
      0.008,
      palette.sageDark,
      Math.sin(angle) * 0.191,
      Math.cos(angle) * 0.191,
      0.048,
      clock,
    );
    tick.rotation.z = -angle;
  }
  const hourHand = new THREE.Group();
  const minuteHand = new THREE.Group();
  clock.add(hourHand, minuteHand);
  box(0.02, 0.115, 0.008, palette.dark, 0, 0.049, 0.055, hourHand, 0.005);
  box(0.014, 0.167, 0.008, palette.dark, 0, 0.071, 0.068, minuteHand, 0.005);
  sphere(0.026, palette.brass, 0, 0, 0.077, clock, [1, 1, 0.4]);

  // Prep island with an open shelf, chopping board, and a folded towel.
  box(1.57, 0.82, 1.05, palette.sageDark, -2.74, 0.53, 0.27, room, 0.04);
  box(1.74, 0.14, 1.25, palette.wood, -2.74, 1.015, 0.27, room, 0.05);
  box(1.35, 0.57, 0.055, palette.dark, -2.74, 0.58, 0.81);
  box(1.39, 0.055, 0.48, palette.wood, -2.74, 0.37, 0.61);
  for (let i = 0; i < 3; i++)
    cylinder(0.24, 0.24, 0.055, palette.ivory, -3.01, 0.43 + i * 0.05, 0.58);
  box(0.46, 0.31, 0.38, palette.terracotta, -2.26, 0.56, 0.57, room, 0.035);
  box(0.65, 0.035, 0.41, palette.woodEdge, -2.98, 1.106, 0.08, room, 0.055);
  box(0.37, 0.025, 0.49, palette.cloth, -2.26, 1.112, 0.52, room, 0.015);
  box(0.37, 0.29, 0.025, palette.cloth, -2.26, 0.975, 0.892, room, 0.01);

  // A laundry corner makes the tablecloth detour visible in the replay.
  box(0.96, 0.98, 0.96, palette.white, -3.65, 0.55, 2.14, room, 0.06);
  box(0.79, 0.13, 0.035, palette.ivory, -3.65, 0.945, 2.637);
  const dryerRing = cylinder(
    0.29,
    0.29,
    0.06,
    palette.metal,
    -3.65,
    0.51,
    2.65,
  );
  dryerRing.rotation.x = Math.PI / 2;
  const dryerGlass = cylinder(
    0.235,
    0.235,
    0.07,
    palette.visor,
    -3.65,
    0.51,
    2.69,
  );
  dryerGlass.rotation.x = Math.PI / 2;
  const dryerCloth = sphere(
    0.15,
    palette.cloth,
    -3.65,
    0.47,
    2.735,
    room,
    [1.25, 0.7, 0.2],
  );
  const laundryLine = box(
    0.025,
    0.025,
    1.55,
    palette.brass,
    -4.135,
    2.12,
    0.12,
  );
  laundryLine.rotation.x = 0.035;
  const lineCloth = box(
    0.035,
    0.66,
    0.74,
    palette.cloth,
    -4.115,
    1.795,
    0.18,
    room,
    0.018,
  );
  for (const z of [-0.1, 0.45])
    box(0.045, 0.115, 0.038, palette.woodEdge, -4.08, 2.105, z);

  // Seven quiet place markers become complete settings as the robot works.
  const tableX = 1.96;
  const tableZ = 1.39;
  box(3.45, 0.14, 1.93, palette.wood, tableX, 1.04, tableZ, room, 0.065);
  for (const x of [0.57, 3.35]) {
    for (const z of [0.72, 2.06])
      box(0.14, 0.99, 0.14, palette.woodEdge, x, 0.515, z, room, 0.023);
  }
  for (const z of [0.73, 1.1, 1.47, 1.84, 2.2])
    box(3.27, 0.003, 0.009, palette.woodGrain, tableX, 1.113, z);
  const tablecloth = new THREE.Group();
  room.add(tablecloth);
  box(
    3.29,
    0.018,
    1.88,
    palette.cloth,
    tableX,
    1.122,
    tableZ,
    tablecloth,
    0.008,
  );
  box(3.28, 0.2, 0.025, palette.cloth, tableX, 1.025, 2.339, tablecloth, 0.009);
  box(0.025, 0.2, 1.9, palette.cloth, 3.611, 1.025, tableZ, tablecloth, 0.009);
  const places = [];
  const markers = [];
  const seats = [
    [0.95, 0.75, 0],
    [1.97, 0.75, 0],
    [2.99, 0.75, 0],
    [0.95, 2.02, Math.PI],
    [1.97, 2.02, Math.PI],
    [2.99, 2.02, Math.PI],
    [0.57, 1.4, Math.PI / 2],
  ];
  for (const [x, z, rotation] of seats) {
    const marker = mesh(
      new THREE.RingGeometry(0.18, 0.195, 40),
      palette.ivory,
      x,
      1.143,
      z,
    );
    marker.rotation.x = -Math.PI / 2;
    markers.push(marker);
    const setting = new THREE.Group();
    setting.position.set(x, 1.143, z);
    setting.rotation.y = rotation;
    room.add(setting);
    cylinder(0.21, 0.185, 0.027, palette.white, 0, 0.017, 0, setting);
    cylinder(0.155, 0.155, 0.011, palette.ivory, 0, 0.037, 0, setting);
    box(0.105, 0.017, 0.17, palette.sageLight, 0, 0.052, 0, setting, 0.012);
    box(0.021, 0.017, 0.29, palette.metal, -0.267, 0.021, 0, setting, 0.007);
    box(
      0.041,
      0.017,
      0.09,
      palette.metal,
      -0.267,
      0.021,
      -0.102,
      setting,
      0.01,
    );
    box(0.026, 0.017, 0.29, palette.metal, 0.267, 0.021, 0, setting, 0.008);
    cylinder(0.062, 0.055, 0.17, palette.glass, 0.25, 0.103, -0.26, setting);
    places.push(setting);

    const chair = new THREE.Group();
    const direction = new THREE.Vector3(0, 0, -0.53).applyAxisAngle(
      new THREE.Vector3(0, 1, 0),
      rotation,
    );
    chair.position.set(x + direction.x, 0, z + direction.z);
    chair.rotation.y = rotation;
    room.add(chair);
    box(0.54, 0.09, 0.49, palette.wood, 0, 0.59, 0, chair, 0.035);
    box(0.51, 0.36, 0.07, palette.sage, 0, 0.98, -0.225, chair, 0.035);
    for (const lx of [-0.21, 0.21]) {
      for (const lz of [-0.18, 0.18])
        box(
          0.06,
          lz < 0 ? 0.93 : 0.53,
          0.06,
          palette.woodEdge,
          lx,
          lz < 0 ? 0.53 : 0.31,
          lz,
          chair,
          0.014,
        );
    }
  }

  const roastMaterial = mat("#b27843");
  const roast = new THREE.Group();
  room.add(roast);
  cylinder(0.39, 0.35, 0.04, palette.ivory, 0, 0.025, 0, roast);
  sphere(0.3, roastMaterial, 0, 0.165, 0, roast, [1, 0.56, 0.7]);
  for (const x of [-0.24, 0.24]) {
    sphere(0.11, roastMaterial, x, 0.115, 0.08, roast, [0.72, 0.72, 1.15]);
    sphere(0.045, palette.ivory, x, 0.11, 0.2, roast, [0.7, 0.7, 1.7]);
  }
  for (let i = 0; i < 6; i++) {
    const angle = (i * Math.PI) / 3;
    sphere(
      0.052,
      i % 2 ? palette.leaf : palette.terracotta,
      Math.cos(angle) * 0.31,
      0.07,
      Math.sin(angle) * 0.26,
      roast,
      [1.3, 0.5, 0.6],
    );
  }

  const crumbleMaterial = mat("#c5a363");
  const crumble = new THREE.Group();
  room.add(crumble);
  cylinder(0.3, 0.25, 0.09, palette.sageDark, 0, 0.055, 0, crumble);
  cylinder(0.277, 0.277, 0.025, crumbleMaterial, 0, 0.114, 0, crumble);
  for (let i = 0; i < 16; i++) {
    const angle = i * 2.4;
    const radius = 0.055 + (i % 4) * 0.052;
    sphere(
      0.035,
      crumbleMaterial,
      Math.cos(angle) * radius,
      0.137,
      Math.sin(angle) * radius,
      crumble,
      [1.2, 0.4, 0.85],
    );
  }

  const stewMaterial = mat("#9d8d46");
  const stew = new THREE.Group();
  stew.position.set(-0.19, 1.225, -2.32);
  room.add(stew);
  cylinder(0.255, 0.21, 0.27, palette.terracotta, 0, 0.14, 0, stew);
  cylinder(0.23, 0.23, 0.015, stewMaterial, 0, 0.276, 0, stew);
  for (const x of [-0.3, 0.3])
    box(0.13, 0.055, 0.12, palette.dark, x, 0.22, 0, stew, 0.025);
  for (let i = 0; i < 7; i++) {
    sphere(
      0.034,
      i % 2 ? palette.leaf : palette.terracotta,
      Math.sin(i * 2.4) * 0.15,
      0.291,
      Math.cos(i * 2.4) * 0.15,
      stew,
      [1, 0.4, 1],
    );
  }

  const salad = new THREE.Group();
  salad.position.set(1.15, 1.146, 1.39);
  room.add(salad);
  cylinder(0.27, 0.16, 0.17, palette.white, 0, 0.1, 0, salad);
  for (let i = 0; i < 10; i++) {
    const angle = i * 2.4;
    sphere(
      0.085,
      i % 3 ? palette.leaf : palette.terracotta,
      Math.cos(angle) * 0.14,
      0.2 + (i % 2) * 0.03,
      Math.sin(angle) * 0.14,
      salad,
      [1, 0.45, 0.8],
    );
  }

  const salt = new THREE.Group();
  salt.position.set(-1.87, 1.12, -2.58);
  room.add(salt);
  cylinder(0.075, 0.085, 0.2, palette.white, 0, 0.11, 0, salt);
  cylinder(0.075, 0.075, 0.045, palette.metal, 0, 0.232, 0, salt);
  const saltWarning = mesh(
    new THREE.TorusGeometry(0.135, 0.019, 8, 32),
    mat("#c8644d"),
    0,
    0.035,
    0,
    salt,
  );
  saltWarning.rotation.x = Math.PI / 2;

  const steam = new THREE.Group();
  room.add(steam);
  const steamMaterial = mat("#fffef2", {
    transparent: true,
    opacity: 0.3,
    depthWrite: false,
  });
  for (let i = 0; i < 5; i++) {
    const puff = sphere(0.065, steamMaterial, 0, 0, 0, steam, [1, 1.4, 1]);
    puff.castShadow = false;
  }

  // Pendant shades and greenery soften the miniature's clean geometry.
  for (const [x, y, z] of [
    [-2.65, 2.94, 0.24],
    [2.03, 3.18, 1.39],
  ]) {
    cylinder(0.012, 0.012, 0.65, palette.dark, x, y + 0.43, z);
    cylinder(0.085, 0.38, 0.26, palette.sageDark, x, y, z);
    cylinder(0.35, 0.35, 0.014, palette.ivory, x, y - 0.134, z);
    sphere(0.075, palette.bulb, x, y - 0.16, z);
  }
  const pendantLight = new THREE.PointLight("#ffe7b2", 3.1, 7, 2);
  pendantLight.position.set(1.8, 2.84, 1.4);
  room.add(pendantLight);
  plant(3.9, 0.05, -0.54, 1.25);

  // The small domestic robot remains the focal point between the two work areas.
  const bot = new THREE.Group();
  room.add(bot);
  const robotBody = new THREE.Group();
  bot.add(robotBody);
  box(0.65, 0.71, 0.51, palette.white, 0, 0.65, 0, robotBody, 0.13);
  box(0.7, 0.47, 0.58, palette.white, 0, 1.2, 0, robotBody, 0.13);
  box(0.56, 0.235, 0.045, palette.visor, 0, 1.21, 0.287, robotBody, 0.07);
  box(0.075, 0.072, 0.015, palette.eye, -0.14, 1.225, 0.318, robotBody, 0.025);
  box(0.075, 0.072, 0.015, palette.eye, 0.14, 1.225, 0.318, robotBody, 0.025);
  box(0.18, 0.035, 0.02, palette.accent, 0, 0.76, 0.26, robotBody, 0.013);
  box(0.11, 0.028, 0.02, palette.sageLight, 0, 0.54, 0.26, robotBody, 0.01);
  cylinder(0.095, 0.095, 0.055, palette.accent, 0, 1.467, 0, robotBody);
  for (const side of [-1, 1]) {
    sphere(0.09, palette.metal, side * 0.364, 1.18, 0, robotBody, [0.4, 1, 1]);
    const arm = mesh(
      new THREE.CapsuleGeometry(0.072, 0.28, 4, 12),
      palette.white,
      side * 0.4,
      0.65,
      0,
      robotBody,
    );
    arm.rotation.z = side * 0.15;
    sphere(0.085, palette.sageLight, side * 0.424, 0.445, 0, robotBody);
  }
  const wheels = [];
  for (const x of [-0.315, 0.315]) {
    const wheelGeometry = new THREE.CylinderGeometry(0.151, 0.151, 0.115, 24);
    wheelGeometry.rotateZ(Math.PI / 2);
    wheels.push(mesh(wheelGeometry, palette.rubber, x, 0.2, 0, bot));
    const hub = cylinder(0.07, 0.07, 0.12, palette.metal, x, 0.2, 0, bot);
    hub.rotation.z = Math.PI / 2;
  }
  const robotRing = mesh(
    new THREE.TorusGeometry(0.43, 0.023, 10, 64),
    palette.accent,
    0,
    0.065,
    0,
    bot,
  );
  robotRing.rotation.x = Math.PI / 2;

  const ambient = new THREE.HemisphereLight("#f9ffef", "#9fafa0", 2.15);
  scene.add(ambient);
  const sunlight = new THREE.DirectionalLight("#fff3d7", 3.35);
  sunlight.position.set(-3, 9, 6);
  sunlight.castShadow = true;
  sunlight.shadow.mapSize.set(2048, 2048);
  Object.assign(sunlight.shadow.camera, {
    left: -7,
    right: 7,
    top: 7,
    bottom: -7,
    near: 0.5,
    far: 24,
  });
  sunlight.shadow.normalBias = 0.03;
  sunlight.shadow.bias = -0.0001;
  sunlight.shadow.radius = 4;
  scene.add(sunlight);
  const fill = new THREE.DirectionalLight("#d9eee7", 0.8);
  fill.position.set(5, 4, -4);
  scene.add(fill);

  const initialKitchen = {
    roast: "absent",
    crumble: "absent",
    stew: "none",
    saltCount: 0,
    cloth: "none",
    places: 0,
    salad: false,
    served: false,
    station: "counter",
  };
  const stations = {
    counter: [-0.97, 0.1, 0.4],
    oven: [-0.62, -1.1, 0.65],
    stove: [0.24, -1.1, 0.45],
    table: [-0.1, 1.89, 0.3],
    laundry: [-2.44, 2.0, 0.9],
  };
  let state = {
    minute: 0,
    playing: false,
    overflow: false,
    powerCut: false,
    kitchen: initialKitchen,
  };
  let elapsed = 0;
  let lastFrame = 0;

  function update({
    minute = 0,
    robot = "Robot",
    color = "#358f7e",
    kitchen = {},
    powerCut = false,
    overflow = false,
    playing = false,
  } = {}) {
    const k = { ...initialKitchen, ...kitchen };
    state = { minute, playing, overflow, powerCut, kitchen: k };
    renderer.domElement.setAttribute(
      "aria-label",
      `${robot}'s kitchen at minute ${Math.round(minute)}. Drag to orbit, scroll to zoom.`,
    );
    const accent = overflow ? "#c86651" : color;
    palette.accent.color.set(accent);
    palette.accent.emissive.set(accent);
    palette.eye.color.set(overflow ? "#ee9e87" : "#a9f0db");
    palette.eye.emissive.set(overflow ? "#df6752" : color);
    palette.eye.emissiveIntensity = overflow ? 0.18 : 0.95;
    robotBody.rotation.z = overflow ? -0.09 : 0;
    const [x, z, yaw] = stations[k.station] || stations.counter;
    bot.position.set(x, 0, z);
    bot.rotation.y = yaw;

    const foodInOven =
      ["in_oven", "overdue"].includes(k.roast) ||
      ["in_oven", "overdue"].includes(k.crumble);
    ovenLight.intensity = foodInOven && !powerCut ? 2.0 : 0;
    ovenIndicator.visible = !powerCut;
    palette.bulb.emissiveIntensity = powerCut ? 0 : 0.7;
    sunlight.intensity = powerCut ? 1.15 : 3.35;
    ambient.intensity = powerCut ? 1.35 : 2.15;
    pendantLight.intensity = powerCut ? 0 : 3.1;

    roast.visible = k.roast !== "absent";
    roast.position.set(
      ...(k.roast === "out" ? [2.86, 1.145, 1.39] : [-0.46, 0.33, -2.35]),
    );
    roast.scale.setScalar(k.roast === "out" ? 1 : 0.85);
    roastMaterial.color.set(k.roast === "overdue" ? "#62483a" : "#b27843");
    crumble.visible = k.crumble !== "absent";
    crumble.position.set(
      ...(k.crumble === "out" ? [-2.76, 1.115, 0.22] : [-0.46, 0.615, -2.37]),
    );
    crumbleMaterial.color.set(k.crumble === "overdue" ? "#715b41" : "#c5a363");
    stew.visible = k.stew !== "none" || k.served;
    stew.position.set(
      ...(k.served ? [1.99, 1.146, 1.39] : [-0.19, 1.225, -2.32]),
    );
    stewMaterial.color.set(k.stew === "butter" ? "#d4b369" : "#9d8d46");
    salad.visible = k.salad;
    saltWarning.visible = k.saltCount > 1;
    tablecloth.visible = k.cloth === "table";
    dryerCloth.visible = k.cloth === "dryer";
    lineCloth.visible = k.cloth === "line";
    for (let i = 0; i < places.length; i++) {
      places[i].visible = i < k.places;
      markers[i].visible = i >= k.places;
    }
    steam.visible = k.stew !== "none" && !powerCut && !overflow;
    steam.position.copy(stew.position);
    steam.position.y += 0.36;
    hourHand.rotation.z = (-(8 + minute / 60) * Math.PI) / 6;
    minuteHand.rotation.z = (-(minute % 60) * Math.PI) / 30;
  }

  function resetCamera() {
    camera.position.set(10, 10, 12);
    controls.target.set(0, 1.12, 0);
    camera.zoom = 1;
    camera.updateProjectionMatrix();
    controls.update();
  }

  function resize() {
    const { width, height } = container.getBoundingClientRect();
    const aspect = Math.max(1, width) / Math.max(1, height);
    const viewHeight = Math.max(7.8, 11.35 / aspect);
    camera.left = (-viewHeight * aspect) / 2;
    camera.right = (viewHeight * aspect) / 2;
    camera.top = viewHeight / 2;
    camera.bottom = -viewHeight / 2;
    camera.updateProjectionMatrix();
    renderer.setSize(Math.max(1, width), Math.max(1, height), false);
  }

  const observer = new ResizeObserver(resize);
  observer.observe(container);
  resetCamera();
  resize();
  update();
  renderer.setAnimationLoop((time) => {
    const delta = lastFrame ? Math.min((time - lastFrame) / 1000, 0.1) : 0;
    lastFrame = time;
    const moving = state.playing && !state.overflow && !state.powerCut;
    if (moving) elapsed += delta;
    const phase = state.minute * 0.15 + elapsed;
    robotBody.position.y =
      moving ? Math.sin(phase * 2.6) * 0.018 : 0;
    robotRing.scale.setScalar(
      state.overflow ? 1 : 1 + Math.sin(phase * 1.8) * 0.035,
    );
    for (let i = 0; i < steam.children.length; i++) {
      const p = (((phase * 0.32 + i / steam.children.length) % 1) + 1) % 1;
      steam.children[i].position.set(
        Math.sin(p * 5 + i) * 0.07,
        p * 0.7,
        Math.cos(p * 4 + i) * 0.05,
      );
      steam.children[i].scale.setScalar(0.5 + p * 1.6);
    }
    for (const wheel of wheels)
      wheel.rotation.x = phase * (moving ? 0.6 : 0);
    controls.update();
    renderer.render(scene, camera);
  });

  function dispose() {
    observer.disconnect();
    renderer.setAnimationLoop(null);
    controls.dispose();
    const geometries = new Set();
    const materials = new Set(Object.values(palette));
    scene.traverse((object) => {
      if (object.geometry) geometries.add(object.geometry);
      if (object.material) {
        for (const material of Array.isArray(object.material)
          ? object.material
          : [object.material])
          materials.add(material);
      }
    });
    for (const geometry of geometries) geometry.dispose();
    for (const material of materials) material.dispose();
    sunlight.shadow.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  }

  return { update, resetCamera, resize, dispose };
}
