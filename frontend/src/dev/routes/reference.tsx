// Sample dev page at /dev/reference: the F-7 reference stringer on its own, for checking the frame.
import { REFERENCE_STRINGER } from "../../three/referenceStringer";
import { Scene } from "../../three/Scene";

export default function Reference() {
  return (
    <div className="p-4">
      <h1 className="mb-2 text-xl font-bold">Reference stringer</h1>
      <p className="mb-2">X red (travel up the ramp), Y green (up), Z blue (the walker's right).</p>
      <Scene parts={[REFERENCE_STRINGER]} height="32rem" />
    </div>
  );
}
