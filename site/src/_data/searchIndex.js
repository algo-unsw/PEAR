// Simple name/alias search (Phase 1): names, aliases and parameter symbols per problem.
import pear from "./pear.js";

export default function () {
  return Object.values(pear().pages).map((p) => ({
    id: p.id,
    names: [p.name, ...p.aliases],
    params: p.parameters.map((q) => q.symbol),
  }));
}
