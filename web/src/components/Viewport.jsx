import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { geometryUrl } from "../lib/client.js";
import { groupColor } from "../lib/palette.js";

const SELECT_EMISSIVE = 0x2a4a6a;

// Libera geometrias e materiais de uma subárvore da cena (GLTF, helpers, marcador).
function disposeSceneResources(root) {
  root.traverse((obj) => {
    obj.geometry?.dispose();
    const m = obj.material;
    if (Array.isArray(m)) m.forEach((x) => x.dispose());
    else m?.dispose();
  });
}

// three.js sanitiza nomes de nó no load do GLTF (remove `.`/`:`/`/`) —
// o nome original (pré-sanitização) fica em userData.name. NUNCA usar obj.name.
function compIdOf(obj) {
  return (obj.userData.name || obj.name).split(".")[0];
}

export default function Viewport({ state, selected, onSelect, preview }) {
  const mountRef = useRef(null);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const meshesByCompRef = useRef(new Map()); // compId -> [meshes]
  const previewGroupRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const controlsRef = useRef(null);
  const contentGroupRef = useRef(null); // grupo único com GLB + grid + marcador + eixos da revision atual
  const framedRef = useRef(false); // já enquadramos a câmera alguma vez? (só no primeiro load com geometria)
  const loadGenRef = useRef(0); // geração da carga em voo — ver comentário no efeito de geometria
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const semSaida = Object.keys(state.group_faces || {}).length === 0;

  // Efeito de montagem única: renderer/câmera/controles/luzes/raycast/loop
  // são criados UMA vez e sobrevivem a toda mutação de estado — antes disto,
  // cada "Aplicar" recriava a cena inteira e resetava a posição da câmera, e
  // os gizmos da Fase 4 (TransformControls) não sobreviveriam por baixo deles.
  useEffect(() => {
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    sceneRef.current = scene;
    scene.background = new THREE.Color(0x16161a);

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / mount.clientHeight,
      1,
      100000,
    );
    camera.up.set(0, 0, 1); // convenção do domínio: Z = altura (Promob)
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(window.devicePixelRatio); // nitidez em telas HiDPI
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controlsRef.current = controls;

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 1.1));
    const dir = new THREE.DirectionalLight(0xffffff, 1.6);
    dir.position.set(1, -2, 3);
    scene.add(dir);

    // seleção por clique (raycast) — drag de órbita não seleciona (limiar 5px).
    // Os listeners são de montagem única: LEEM meshesByCompRef.current a cada
    // clique (não um mapa fechado em closure), porque o efeito de geometria
    // substitui esse mapa a cada troca de revision. A câmera usada aqui é a
    // instância persistente — sem problema de closure porque nunca é recriada.
    const raycaster = new THREE.Raycaster();
    const down = { x: 0, y: 0 };
    const onPointerDown = (e) => {
      if (e.button !== 0) return; // só botão esquerdo seleciona (direito/meio = órbita)
      down.x = e.clientX;
      down.y = e.clientY;
    };
    const onPointerUp = (e) => {
      if (e.button !== 0) return;
      if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(ndc, camera);
      const meshes = [...meshesByCompRef.current.values()].flat().filter((m) => m.visible);
      const hits = raycaster.intersectObjects(meshes, false);
      onSelectRef.current(hits.length > 0 ? compIdOf(hits[0].object) : null);
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);

    let frame;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      controls.dispose();
      previewGroupRef.current = null;
      contentGroupRef.current = null;
      sceneRef.current = null;
      cameraRef.current = null;
      controlsRef.current = null;
      disposeSceneResources(scene);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      meshesByCompRef.current = new Map();
    };
  }, []);

  // Efeito de geometria: troca APENAS o grupo de conteúdo (GLB + grid +
  // marcador de origem + eixos) a cada mutação — renderer/câmera/controles
  // persistem por cima, então a posição da câmera sobrevive a um "Aplicar".
  useEffect(() => {
    setErro(null);
    setAviso(null);
    const scene = sceneRef.current;
    const camera = cameraRef.current;
    const controls = controlsRef.current;

    // geração desta carga: pode haver DUAS cargas em voo (revision N ainda
    // buscando o GLB quando o usuário já disparou N+1) — um boolean
    // "cancelled" simples não distingue as duas, um contador distingue.
    const myGen = ++loadGenRef.current;

    // remove e descarta o grupo de conteúdo anterior (tudo que ele contém:
    // GLB antigo, grid, marcador, eixos) antes de montar o novo, vazio
    if (contentGroupRef.current) {
      scene.remove(contentGroupRef.current);
      disposeSceneResources(contentGroupRef.current);
    }
    const group = new THREE.Group();
    contentGroupRef.current = group;
    scene.add(group);

    const meshesByComp = new Map();
    meshesByCompRef.current = meshesByComp;

    // sem peças no resultado (tudo removido ou sem grupo): não há GLB para
    // buscar — o backend responde 404 — só avisa o usuário e deixa o grupo vazio
    if (semSaida) {
      setAviso("nenhuma peça no resultado");
      return () => {
        loadGenRef.current++; // nada em voo aqui, mas mantém a geração monotônica
      };
    }

    const groupNames = state.groups.map((g) => g.name);
    const groupOf = {};
    for (const c of state.components) groupOf[c.id] = c.group;

    new GLTFLoader().load(
      geometryUrl(state.revision),
      (gltf) => {
        if (loadGenRef.current !== myGen) {
          // outra troca de geometria (ou o unmount) já invalidou esta carga
          disposeSceneResources(gltf.scene);
          return;
        }
        gltf.scene.traverse((obj) => {
          if (obj.isMesh) {
            // o GLB do backend traz só POSITION — sem normais o material
            // iluminado renderiza preto
            if (!obj.geometry.attributes.normal) {
              obj.geometry.computeVertexNormals();
            }
            const compId = compIdOf(obj);
            obj.material = new THREE.MeshStandardMaterial({
              color: groupColor(groupOf[compId], groupNames),
              metalness: 0.1,
              roughness: 0.75,
              side: THREE.DoubleSide,
            });
            if (!meshesByComp.has(compId)) meshesByComp.set(compId, []);
            meshesByComp.get(compId).push(obj);
            // seleção pode já existir quando a geometria recarrega (ex.: após Aplicar)
            if (compId === selectedRef.current) {
              obj.material.emissive.setHex(SELECT_EMISSIVE);
            }
          }
        });
        group.add(gltf.scene);

        const box = new THREE.Box3().setFromObject(gltf.scene);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const radius = Math.max(size.x, size.y, size.z, 1);

        // grid no plano XY (chão da convenção Z-up)
        const grid = new THREE.GridHelper(radius * 3, 30, 0x3a3a46, 0x26262e);
        grid.rotation.x = Math.PI / 2; // GridHelper nasce em XZ; deitar para XY
        group.add(grid);

        // marcador de origem: quadrado vermelho em (0,0,0), como o Promob mostra
        const marker = new THREE.Mesh(
          new THREE.PlaneGeometry(radius * 0.04, radius * 0.04),
          new THREE.MeshBasicMaterial({
            color: 0xff2222,
            side: THREE.DoubleSide,
            depthTest: false,
          }),
        );
        marker.renderOrder = 999;
        group.add(marker);

        group.add(new THREE.AxesHelper(radius * 0.5));

        // câmera: só enquadra no primeiro load com geometria desta sessão de
        // viewport — trocas seguintes (ex.: depois de "Aplicar") preservam a
        // posição/target que o usuário já ajustou
        if (!framedRef.current && !box.isEmpty()) {
          camera.position.set(
            center.x + radius * 1.2,
            center.y - radius * 1.2,
            center.z + radius * 0.9,
          );
          controls.target.copy(center);
          controls.update();
          framedRef.current = true;
        }
      },
      undefined,
      (err) => {
        console.error("falha ao carregar", geometryUrl(state.revision), err);
        if (loadGenRef.current === myGen) {
          setErro("falha ao carregar a geometria — veja o console");
        }
      },
    );

    return () => {
      // invalida esta geração — protege o callback do GLTFLoader que chegar
      // depois de outra troca de geometria (ou depois do unmount)
      loadGenRef.current++;
    };
  }, [state]);

  // destaque emissivo da família selecionada — não recria a cena
  useEffect(() => {
    selectedRef.current = selected;
    for (const [compId, meshes] of meshesByCompRef.current) {
      for (const m of meshes) {
        m.material.emissive?.setHex(compId === selected ? SELECT_EMISSIVE : 0x000000);
      }
    }
  }, [selected, state]);

  // overlay de preview: "depois" esconde as originais da família e mostra o
  // GLB pré-visualizado; "antes" (ou sem preview) restaura as originais
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    const restore = () => {
      if (previewGroupRef.current) {
        scene.remove(previewGroupRef.current);
        disposeSceneResources(previewGroupRef.current);
        previewGroupRef.current = null;
      }
      for (const meshes of meshesByCompRef.current.values()) {
        for (const m of meshes) m.visible = true;
      }
    };
    restore();
    if (!preview || preview.mostrando !== "depois") return;

    const originals = meshesByCompRef.current.get(preview.componentId) || [];
    for (const m of originals) m.visible = false;

    const groupNames = state.groups.map((g) => g.name);
    const groupOf = {};
    for (const c of state.components) groupOf[c.id] = c.group;
    let disposed = false;
    new GLTFLoader().load(
      preview.url,
      (gltf) => {
        if (disposed) {
          disposeSceneResources(gltf.scene);
          return;
        }
        gltf.scene.traverse((obj) => {
          if (obj.isMesh) {
            if (!obj.geometry.attributes.normal) obj.geometry.computeVertexNormals();
            obj.material = new THREE.MeshStandardMaterial({
              color: groupColor(groupOf[preview.componentId], groupNames),
              emissive: SELECT_EMISSIVE,
              metalness: 0.1,
              roughness: 0.75,
              side: THREE.DoubleSide,
            });
          }
        });
        previewGroupRef.current = gltf.scene;
        scene.add(gltf.scene); // fora do grupo de conteúdo — sobrevive à troca de geometria por si só
      },
      undefined,
      (err) => console.error("falha ao carregar o preview", err),
    );
    return () => {
      disposed = true;
      restore();
    };
  }, [preview, state]);

  return (
    <div className="viewport" ref={mountRef}>
      {erro && <div className="viewport-erro">{erro}</div>}
      {!erro && aviso && <div className="viewport-aviso">{aviso}</div>}
    </div>
  );
}
