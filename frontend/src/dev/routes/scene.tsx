import { useEffect, useState } from "react";
import type { GenerateResponse } from "../../types";
import { Scene } from "../../three/Scene";

export default function SceneCheck() {
  const [models, setModels] = useState<GenerateResponse[]>([]);
  useEffect(() => { void Promise.all([fetch("/fixtures/specs/ramp_straight.json"), fetch("/fixtures/specs/ramp_switchback.json")]).then(async (responses) => setModels(await Promise.all(responses.map((response) => response.json() as Promise<GenerateResponse>)))); }, []);
  return <main className="space-y-6 p-4"><h1 className="text-2xl font-bold">Scene fixture check</h1>{models.map((model) => <section key={String(model.spec.params.layout?.value)} className="app-card p-3"><h2 className="text-lg font-bold">{String(model.spec.params.layout?.value)} ramp</h2><Scene parts={model.spec.parts} height="32rem" /></section>)}</main>;
}
