// One entry per problem page, for pagination.
import pear from "./pear.js";

export default function () {
  return Object.values(pear().pages);
}
