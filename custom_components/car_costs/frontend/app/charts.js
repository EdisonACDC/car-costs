/* Small SVG charts (no libraries): bars, lines, donut. Colours come from CSS variables. */

import { eur, num, monthLabel, dateLabel, parseDay } from "./i18n.js";

let uid = 0;
const W = 320;

/** Grouped bars: months × two series (old car red, new car green gradient). */
export function barsChart(months, { height = 120, a, b }) {
  const id = `bc${++uid}`;
  const pad = 18;
  const h = height;
  const max = Math.max(1, ...months.flatMap((m) => [m[a.key], m[b.key]]));
  const gw = W / Math.max(1, months.length);
  const bw = Math.min(22, gw * 0.32);
  const y = (v) => pad + (h - pad - 6) * (1 - v / max);
  const rects = months.map((m, i) => {
    const cx = gw * i + gw / 2;
    const tip = `${monthLabel(m.month)} · ${a.label} ${eur(m[a.key])} · ${b.label} ${eur(m[b.key])}`;
    const bar = (v, x, fill) => `<rect x="${x}" y="${y(v)}" width="${bw}" height="${Math.max(2, h - 6 - y(v))}" rx="6" fill="${fill}"/>`;
    return `<g class="tap" data-tip="${tip}"><rect x="${gw * i}" y="0" width="${gw}" height="${h}" fill="transparent"/>
      ${bar(m[a.key], cx - bw - 2, a.fill)}${bar(m[b.key], cx + 2, b.fill)}
      <text x="${cx}" y="${h + 12}" text-anchor="middle" class="axis">${monthLabel(m.month, false)}</text></g>`;
  }).join("");
  return `<svg viewBox="0 0 ${W} ${h + 18}" role="img" aria-label="${a.label} / ${b.label}">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7ee8fa"/><stop offset="1" stop-color="#5ef0a0"/></linearGradient></defs>
    ${rects.replaceAll("url(#new)", `url(#${id})`)}</svg>`;
}

/** Lines over time. series: [{points:[{t:Date,y}], color, dash?, area?}], goal: {y,label} */
export function lineChart(series, { height = 150, goal = null, yFmt = (v) => num(v, 0) } = {}) {
  const id = `lc${++uid}`;
  const all = series.flatMap((s) => s.points);
  if (all.length < 2) return "";
  const t0 = Math.min(...all.map((p) => +p.t)), t1 = Math.max(...all.map((p) => +p.t));
  let lo = Math.min(0, ...all.map((p) => p.y)), hi = Math.max(...all.map((p) => p.y), goal ? goal.y : -Infinity);
  if (hi <= lo) hi = lo + 1;
  const L = 34, R = 8, T = 10, B = 20, h = height;
  const x = (t) => L + ((+t - t0) / Math.max(1, t1 - t0)) * (W - L - R);
  const y = (v) => T + (h - T - B) * (1 - (v - lo) / (hi - lo));
  const grid = [0, 0.5, 1].map((f) => {
    const v = lo + (hi - lo) * f;
    return `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" class="grid"/><text x="${L - 4}" y="${y(v) + 3}" text-anchor="end" class="axis">${yFmt(v)}</text>`;
  }).join("");
  const paths = series.map((s, i) => {
    const d = s.points.map((p, j) => `${j ? "L" : "M"}${x(p.t).toFixed(1)} ${y(p.y).toFixed(1)}`).join("");
    const area = s.area ? `<path d="${d}L${x(s.points.at(-1).t)} ${y(lo)}L${x(s.points[0].t)} ${y(lo)}Z" fill="url(#${id}${i})" opacity=".45"/>
      <defs><linearGradient id="${id}${i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:${s.color}"/><stop offset="1" style="stop-color:${s.color};stop-opacity:0"/></linearGradient></defs>` : "";
    return `${area}<path d="${d}" fill="none" style="stroke:${s.color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" ${s.dash ? 'stroke-dasharray="5 4"' : ""}/>`;
  }).join("");
  const goalLine = goal
    ? `<line x1="${L}" x2="${W - R}" y1="${y(goal.y)}" y2="${y(goal.y)}" style="stroke:var(--gold)" stroke-width="1.5" stroke-dasharray="4 4"/>
       <text x="${W - R}" y="${y(goal.y) - 4}" text-anchor="end" class="axis" style="fill:var(--gold);opacity:1">${goal.label}</text>` : "";
  const iso = (t) => new Date(t).toISOString().slice(0, 10);
  const lastX = x(t1), lastP = series[0].points.at(-1);
  return `<svg viewBox="0 0 ${W} ${h}" role="img">${grid}${goalLine}${paths}
    <circle cx="${lastX}" cy="${y(lastP.y)}" r="4" style="fill:${series[0].color}" stroke="#fff" stroke-width="1.5"/>
    <text x="${L}" y="${h - 4}" class="axis">${dateLabel(iso(t0), false)}</text>
    <text x="${W - R}" y="${h - 4}" text-anchor="end" class="axis">${dateLabel(iso(t1), false)}</text></svg>`;
}

/** Donut: parts [{value,color,label}] */
export function donut(parts, centerTop, centerBottom) {
  const total = parts.reduce((s, p) => s + p.value, 0);
  if (total <= 0) return "";
  const r = 52, c = 2 * Math.PI * r;
  let off = 0;
  const arcs = parts.filter((p) => p.value > 0).map((p) => {
    const len = (p.value / total) * c;
    const el = `<circle cx="70" cy="70" r="${r}" fill="none" style="stroke:${p.color}" stroke-width="18" stroke-dasharray="${Math.max(0, len - 2)} ${c}" stroke-dashoffset="${-off}" class="tap" data-tip="${p.label} · ${eur(p.value)} · ${num((p.value / total) * 100, 0)}%"/>`;
    off += len;
    return el;
  }).join("");
  return `<svg viewBox="0 0 140 140" role="img"><g transform="rotate(-90 70 70)">${arcs}</g>
    <text x="70" y="68" text-anchor="middle" class="donut-v">${centerTop}</text>
    <text x="70" y="86" text-anchor="middle" class="axis">${centerBottom}</text></svg>`;
}
export { parseDay };
