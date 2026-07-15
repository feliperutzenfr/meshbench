import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { groupColor } from "../lib/palette.js";

export default function Viewport({ state }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x16161a);

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / mount.clientHeight,
      1,
      100000,
    );
    camera.up.set(0, 0, 1); // convenção do domínio: Z = altura (Promob)

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 1.1));
    const dir = new THREE.DirectionalLight(0xffffff, 1.6);
    dir.position.set(1, -2, 3);
    scene.add(dir);

    const groupNames = state.groups.map((g) => g.name);
    const groupOf = {};
    for (const c of state.components) groupOf[c.id] = c.group;

    new GLTFLoader().load("/api/project/geometry", (gltf) => {
      gltf.scene.traverse((obj) => {
        if (obj.isMesh) {
          const compId = obj.name.split(".")[0];
          obj.material = new THREE.MeshStandardMaterial({
            color: groupColor(groupOf[compId], groupNames),
            metalness: 0.1,
            roughness: 0.75,
            side: THREE.DoubleSide,
          });
        }
      });
      scene.add(gltf.scene);

      const box = new THREE.Box3().setFromObject(gltf.scene);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z, 1);

      // grid no plano XY (chão da convenção Z-up)
      const grid = new THREE.GridHelper(radius * 3, 30, 0x3a3a46, 0x26262e);
      grid.rotation.x = Math.PI / 2; // GridHelper nasce em XZ; deitar para XY
      scene.add(grid);

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
      scene.add(marker);

      scene.add(new THREE.AxesHelper(radius * 0.5));

      camera.position.set(
        center.x + radius * 1.2,
        center.y - radius * 1.2,
        center.z + radius * 0.9,
      );
      controls.target.copy(center);
      controls.update();
    });

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
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [state]);

  return <div className="viewport" ref={mountRef} />;
}
