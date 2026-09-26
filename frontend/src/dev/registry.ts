// Dev-only pages, found automatically: every file in `dev/routes/` whose default export is a React
// component is served at `/dev/<file name>` by `npm run dev` (for example `routes/scene.tsx` at
// `/dev/scene`). Nobody edits this file; to add a page, add a file. Not available in production builds.
import type { ComponentType } from "react";

const modules = import.meta.glob<{ default: ComponentType }>("./routes/*.tsx", { eager: true });

export const DEV_ROUTES: Record<string, ComponentType> = Object.fromEntries(
  Object.entries(modules).map(([file, mod]) => [`/dev/${file.replace("./routes/", "").replace(/\.tsx$/, "")}`, mod.default]),
);
