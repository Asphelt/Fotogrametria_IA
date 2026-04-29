/* ── Visor 3D con Three.js r128 desde CDN ── */
let scene, camera, renderer, controls;
let visorIniciado = false;

function initVisor() {
  if (visorIniciado) return;
  visorIniciado = true;

  const wrap = document.getElementById('viewer-wrap') || document.querySelector('.viewer-wrap');
  const canvas = document.getElementById('visor3d');

  /* Escena */
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0c14);
  scene.fog = new THREE.FogExp2(0x0a0c14, 0.04);

  /* Cámara */
  camera = new THREE.PerspectiveCamera(45, canvas.offsetWidth / canvas.offsetHeight, 0.01, 500);
  camera.position.set(3, 2, 3);

  /* Renderer */
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
  renderer.setSize(canvas.offsetWidth, canvas.offsetHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputEncoding = THREE.sRGBEncoding;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;

  /* Luces */
  const ambient = new THREE.AmbientLight(0xffffff, 0.4);
  scene.add(ambient);

  const key = new THREE.DirectionalLight(0xffffff, 1.0);
  key.position.set(5, 8, 5);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  scene.add(key);

  const fill = new THREE.DirectionalLight(0x4488ff, 0.3);
  fill.position.set(-5, 3, -5);
  scene.add(fill);

  const rim = new THREE.DirectionalLight(0xffaa44, 0.2);
  rim.position.set(0, -3, -8);
  scene.add(rim);

  /* Grid */
  const grid = new THREE.GridHelper(20, 40, 0x2a3055, 0x1e2440);
  grid.position.y = -0.01;
  scene.add(grid);

  /* Controles de órbita */
  controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 0.3;
  controls.maxDistance = 100;
  controls.maxPolarAngle = Math.PI * 0.9;
  controls.screenSpacePanning = true;

  /* Loop de animación */
  (function animar() {
    requestAnimationFrame(animar);
    controls.update();
    renderer.render(scene, camera);
  })();

  /* Resize */
  const observer = new ResizeObserver(() => {
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
  observer.observe(canvas.parentElement);
}

function cargarModelo(jobId) {
  const loader = new THREE.GLTFLoader();
  const loaderEl = document.getElementById('viewer-loader');

  loader.load(
    `/modelo/${jobId}`,
    (gltf) => {
      /* Limpiar modelos anteriores */
      scene.children
        .filter(c => c.userData.esModelo)
        .forEach(c => scene.remove(c));

      const model = gltf.scene;
      model.userData.esModelo = true;

      /* Habilitar sombras en la malla */
      model.traverse(node => {
        if (node.isMesh) {
          node.castShadow = true;
          node.receiveShadow = true;
        }
      });

      /* Centrar modelo en el origen */
      const box = new THREE.Box3().setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z);
      const scale = maxDim > 0 ? 2 / maxDim : 1;

      model.scale.setScalar(scale);
      model.position.sub(center.multiplyScalar(scale));

      scene.add(model);

      /* Ajustar cámara */
      const dist = 2.5;
      camera.position.set(dist, dist * 0.7, dist);
      controls.target.set(0, 0, 0);
      controls.update();

      /* Ocultar loader */
      if (loaderEl) loaderEl.style.display = 'none';
    },
    (xhr) => {
      if (loaderEl && xhr.total) {
        const pct = Math.round(xhr.loaded / xhr.total * 100);
        const p = loaderEl.querySelector('p');
        if (p) p.textContent = `Cargando modelo… ${pct}%`;
      }
    },
    (err) => {
      console.error('Error cargando modelo:', err);
      if (loaderEl) {
        loaderEl.querySelector('p').textContent = 'Error al cargar el modelo';
        loaderEl.querySelector('.spinner').style.display = 'none';
      }
    }
  );
}

function descargarModelo() {
  if (typeof trabajoActualId !== 'undefined' && trabajoActualId) {
    const a = document.createElement('a');
    a.href = `/modelo/${trabajoActualId}`;
    a.download = `modelo_3d_${trabajoActualId.slice(0,8)}.glb`;
    a.click();
  }
}
