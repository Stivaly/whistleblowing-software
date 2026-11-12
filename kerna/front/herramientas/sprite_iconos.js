// Genera el sprite SVG con los íconos de Lucide listados en iconos.txt. Uso: node sprite_iconos.js lucide.js iconos.txt salida.svg
const fs = require("fs");
const [, , lib, lista, salida] = process.argv;
const L = require(lib);
const pas = (n) => n.split("-").map((s) => s[0].toUpperCase() + s.slice(1)).join("");
const nombres = fs.readFileSync(lista, "utf8").split(/\s+/).filter(Boolean);
let out = '<svg xmlns="http://www.w3.org/2000/svg" style="display:none">\n';
for (const n of nombres) {
  const d = L[pas(n)];
  if (!d) { console.error("falta el ícono " + n); process.exit(1); }
  const hijos = d[2].map(([t, a]) => "<" + t + " " + Object.entries(a).map(([k, v]) => k + '="' + v + '"').join(" ") + "/>").join("");
  out += '<symbol id="' + n + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + hijos + "</symbol>\n";
}
fs.writeFileSync(salida, out + "</svg>\n");
console.log(nombres.length + " íconos");
