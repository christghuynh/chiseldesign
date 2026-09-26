// Part -> three.js geometry and placement.
//
// A Part is a CCW XY `profile` extruded along local +Z by `thickness`, rotated by Euler XYZ
// (radians; three.js order "XYZ", i.e. matrix Rx*Ry*Rz) and then translated by `pos`.
// The world frame is Y-up, in inches, so the scene needs no axis conversion.
import * as THREE from "three";
import type { Part } from "../types";

export function partGeometry(part: Part): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape(part.profile.map(([x, y]) => new THREE.Vector2(x, y)));
  return new THREE.ExtrudeGeometry(shape, { depth: part.thickness, bevelEnabled: false, steps: 1 });
}

/** Places an object exactly as the R3F <mesh position rotation> props do (default Euler order XYZ). */
export function applyPartTransform(object: THREE.Object3D, part: Part): void {
  const [px, py, pz] = part.transform.pos;
  const [rx, ry, rz] = part.transform.rot;
  object.position.set(px, py, pz);
  object.rotation.set(rx, ry, rz);
}

/** Unique world-space vertices of a part, sorted, for tests and picking. */
export function partWorldVertices(part: Part): [number, number, number][] {
  const geometry = partGeometry(part);
  const mesh = new THREE.Mesh(geometry);
  applyPartTransform(mesh, part);
  mesh.updateMatrixWorld(true);

  const positions = geometry.getAttribute("position");
  const unique = new Map<string, [number, number, number]>();
  const v = new THREE.Vector3();
  for (let i = 0; i < positions.count; i++) {
    v.fromBufferAttribute(positions, i).applyMatrix4(mesh.matrixWorld);
    const point: [number, number, number] = [
      Math.round(v.x * 1e4) / 1e4 + 0,
      Math.round(v.y * 1e4) / 1e4 + 0,
      Math.round(v.z * 1e4) / 1e4 + 0,
    ];
    unique.set(point.map((n) => n.toFixed(4)).join(","), point);
  }
  geometry.dispose();
  return [...unique.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1] || a[2] - b[2]);
}
