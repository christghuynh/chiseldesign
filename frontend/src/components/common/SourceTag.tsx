import type { ParamValue } from "../../types";

export function SourceTag({ source }: Pick<ParamValue, "source">) {
  return <span className="source-tag">{source}</span>;
}
