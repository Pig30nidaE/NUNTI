/* Route-volume formation. Pure geometry is shared with the browser key-pose checks.
 * Canvas paints a changing closed body, not a mask revealing the final bitmap.
 * LottieFiles motion-design principles: one hero, anticipation, material weight,
 * delayed appendages, a quiet contact shadow, and a static reduced-motion finish.
 */
(function installFormation(scope) {
  'use strict';
  const clamp = value => Math.max(0, Math.min(1, value));
  const smooth = value => { const x = clamp(value); return x * x * (3 - 2 * x); };
  const mix = (a, b, t) => t === 0 ? [...a] : t === 1 ? [...b] : [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
  const distance = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
  const validPoint = p => Array.isArray(p) && p.length === 2 && p.every(n => Number.isFinite(n) && n >= 0 && n <= 1);
  function lengths(points) {
    const cumulative = [0];
    for (let i = 1; i < points.length; i++) cumulative.push(cumulative[i - 1] + distance(points[i - 1], points[i]));
    return { cumulative, total: cumulative.at(-1) };
  }
  function atArc(points, arc, measure = lengths(points)) {
    const target = clamp(arc) * measure.total;
    if (target === 0) return [...points[0]];
    if (target >= measure.total) return [...points.at(-1)];
    let i = 1;
    while (i < points.length - 1 && measure.cumulative[i] < target) i++;
    const start = measure.cumulative[i - 1], span = measure.cumulative[i] - start;
    return mix(points[i - 1], points[i], span ? (target - start) / span : 0);
  }
  function resample(points, count) {
    const measure = lengths(points);
    return Array.from({ length: count }, (_, i) => atArc(points, i / (count - 1), measure));
  }
  function atIndex(points, fraction) {
    const value = clamp(fraction) * (points.length - 1), index = Math.floor(value);
    return index >= points.length - 1 ? [...points.at(-1)] : mix(points[index], points[index + 1], value - index);
  }
  function trace(points, progress) {
    const measure = lengths(points), target = clamp(progress) * measure.total;
    const output = [[...points[0]]];
    if (!target) return output;
    for (let i = 1; i < points.length; i++) {
      if (measure.cumulative[i] < target) output.push([...points[i]]);
      else { output.push(atArc(points, progress, measure)); break; }
    }
    return output;
  }
  function fitRoute(points) {
    const xs = points.map(p => p[0]), ys = points.map(p => p[1]);
    const dx = Math.max(...xs) - Math.min(...xs), dy = Math.max(...ys) - Math.min(...ys);
    const factor = .76 / Math.max(dx, dy, .0001);
    const cx = (Math.max(...xs) + Math.min(...xs)) / 2, cy = (Math.max(...ys) + Math.min(...ys)) / 2;
    return points.map(p => [.5 + (p[0] - cx) * factor, .48 + (p[1] - cy) * factor]);
  }
  function project(point, spine) {
    let best = null;
    for (let i = 1; i < spine.length; i++) {
      const a = spine[i - 1], b = spine[i], dx = b[0] - a[0], dy = b[1] - a[1];
      const length2 = dx * dx + dy * dy;
      const t = length2 ? clamp(((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length2) : 0;
      const p = mix(a, b, t), error = distance(point, p);
      if (!best || error < best.error) best = { error, point: p, arc: (i - 1 + t) / (spine.length - 1) };
    }
    return best;
  }
  function area(points) {
    let sum = 0;
    for (let i = 1; i < points.length; i++) sum += points[i - 1][0] * points[i][1] - points[i][0] * points[i - 1][1];
    return Math.abs(sum) / 2;
  }
  function corridorLinks(contour, spine) {
    const n = contour.length - 1;
    const nearest = point => { let best = 0; for (let i = 1; i < n; i++) if (distance(contour[i], point) < distance(contour[best], point)) best = i; return best; };
    const first = nearest(spine[0]);
    let last = nearest(spine.at(-1));
    if (last === first) last = (first + Math.floor(n / 2)) % n;
    const links = new Array(n);
    for (const direction of [1, -1]) {
      const indices = [first];
      while (indices.at(-1) !== last) indices.push((indices.at(-1) + direction + n) % n);
      const boundary = indices.map(i => contour[i]), measure = lengths(boundary);
      indices.forEach((index, i) => {
        const arc = measure.total ? measure.cumulative[i] / measure.total : i / (indices.length - 1);
        const center = atIndex(spine, arc);
        links[index] = { arc, side: direction, offset: [contour[index][0] - center[0], contour[index][1] - center[1]] };
      });
    }
    links.push({ ...links[0], offset: [...links[0].offset] });
    return links;
  }
  function prepare(artifact) {
    const f = artifact?.design?.formation, route = artifact?.route?.points;
    const measured = artifact?.mediaOrigin === 'LOCAL_MODEL';
    if ((!measured && artifact?.mediaOrigin !== 'LOCAL_RENDER') || f?.version !== 'route-volume-2') return null;
    if (measured && (f.source !== 'MEASURED_ALPHA_BOUNDARY' || f.mapping !== 'GEOMETRIC_PROJECTION_NOT_SEMANTIC')) return null;
    const faceProtected = measured ? f.faceCenterVerified === true : f.faceCenterVerified !== false;
    if (!Array.isArray(f.contour) || f.contour.length < 128 || f.contour.length > 256 ||
        !Array.isArray(f.spine) || f.spine.length < 64 || f.spine.length > 128 ||
        !Array.isArray(route) || route.length < 2 || route.length > 512 ||
        ![...f.contour, ...f.spine, ...route].every(validPoint) || (faceProtected && !validPoint(f.faceCenter)) ||
        distance(f.contour[0], f.contour.at(-1)) > .00001 || area(f.contour) < .001 ||
        !Array.isArray(f.palette) || f.palette.length < 2 || !f.palette.every(c => /^#[0-9a-f]{6}$/i.test(c))) return null;
    const contour = f.contour.map(p => [...p]), spine = f.spine.map(p => [...p]), raw = fitRoute(route);
    const spineMeasure = lengths(spine);
    if (spineMeasure.total < .001 || lengths(raw).total < .001) return null;
    // Both contour sides traverse the same route once in opposite directions.
    // Independent nearest-point projection can jump between bends and fill a phantom polygon.
    const links = corridorLinks(contour, spine);
    const faceCenter = faceProtected ? [...f.faceCenter] : null;
    const faceLink = faceProtected ? project(faceCenter, spine) : null;
    const center = [(Math.min(...contour.map(p => p[0])) + Math.max(...contour.map(p => p[0]))) / 2,
      (Math.min(...contour.map(p => p[1])) + Math.max(...contour.map(p => p[1]))) / 2];
    const effectSeeds=Array.from({length:54},(_,i)=>{const arc=(i*.61803398875)%1;return {
      phase:i*2.399963229728653,route:atArc(raw,arc),target:contour[Math.floor(arc*(contour.length-1))]};});
    return { contour, spine, raw, rawMeasure: lengths(raw), spineMeasure, links,
      faceCenter, faceLink, faceProtected, center, source: measured ? f.source : 'LOCAL_RENDER_GEOMETRY',
      mapping: measured ? f.mapping : 'SOURCE_ROUTE_ARC_CORRESPONDENCE', palette: [...f.palette], sampleCount: spine.length,
      sourceSamples: resample(raw, spine.length), finalArea: area(contour), effectSeeds,
      character: artifact.design.characterPlan || null };
  }
  function pose(plan, progress) {
    if (!Number.isFinite(progress) || progress < 0 || progress > 1) throw new RangeError('formation progress');
    const p = progress, fold = smooth((p - .20) / .32), inflate = smooth((p - .28) / .46);
    const preparePulse = Math.sin(clamp((p - .14) / .12) * Math.PI) * .008;
    const centerAt = arc => {
      // Renderer spine samples are indexed by the ORIGINAL route arc, not the rest-pose arc.
      const a = atArc(plan.raw, arc, plan.rawMeasure), b = atIndex(plan.spine, arc);
      const middle = mix(a, b, .5);
      middle[1] -= Math.sin(Math.PI * arc) * .025;
      const result = fold < .5 ? mix(a, middle, smooth(fold * 2)) : mix(middle, b, smooth((fold - .5) * 2));
      result[1] += preparePulse * (arc - .5);
      return result;
    };
    const secondaryT = clamp((p - .66) / .16);
    const secondary = Math.sin(secondaryT * Math.PI * 2) * Math.exp(-secondaryT * 4) * (1 - secondaryT) * inflate;
    const contour = p >= .82 ? plan.contour.map(v => [...v]) : plan.links.map((link, index) => {
      const center = centerAt(link.arc), v = plan.contour[index];
      const before = centerAt(Math.max(0, link.arc - .005)), after = centerAt(Math.min(1, link.arc + .005));
      const length = Math.max(.0001, distance(before, after));
      const narrow = .003 * link.side * Math.sin(Math.PI * link.arc) * (1 - inflate);
      const upper = plan.faceProtected ? clamp((plan.faceCenter[1] - .04 - v[1]) / .12) : 0;
      return [center[0] + link.offset[0] * inflate - (after[1] - before[1]) / length * narrow + secondary * upper * (v[0] < (plan.faceCenter?.[0] ?? .5) ? -.008 : .008),
        center[1] + link.offset[1] * inflate + (after[0] - before[0]) / length * narrow - secondary * upper * .015];
    });
    const centerline = Array.from({ length: plan.sampleCount }, (_, i) => centerAt(i / (plan.sampleCount - 1)));
    const faceBase = plan.faceProtected ? centerAt(plan.faceLink.arc) : null;
    const faceCenter = !plan.faceProtected ? null : p >= .74 ? [...plan.faceCenter] : [faceBase[0] + (plan.faceCenter[0] - plan.faceLink.point[0]) * inflate,
      faceBase[1] + (plan.faceCenter[1] - plan.faceLink.point[1]) * inflate];
    const landingT = clamp((p - .78) / .22);
    const landing = p === 1 ? 0 : Math.sin(landingT * Math.PI * 2) * Math.exp(-landingT * 5) * (1 - landingT);
    return { contour, centerline, faceCenter, fold, inflate, imageWeight: smooth((p - .82) / .12),
      bodyOpacity: smooth((p - .24) / .08), faceOpacity: plan.faceProtected ? smooth((p - .70) / .10) : 0,
      guideOpacity: (1 - fold) * .24, strokeOpacity: 1 - smooth((p - .28) / .18),
      traceFraction: smooth(p / .32), scaleX: 1 + landing * .026, scaleY: 1 / (1 + landing * .026),
      floatY: landing * .013, area: area(contour), progress: p };
  }
  function path(ctx, points, close = false) {
    ctx.beginPath(); ctx.moveTo(...points[0]);
    for (let i = 1; i < points.length; i++) ctx.lineTo(...points[i]);
    if (close) ctx.closePath();
  }
  const rgb = hex => [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const rgba = (hex, a) => `rgba(${rgb(hex).join(',')},${a})`;
  const tint = (hex, amount) => `rgb(${rgb(hex).map(v => Math.round(v + (255 - v) * amount)).join(',')})`;
  const effectStyles = ['STARDUST', 'PETAL_BLOOM', 'AURORA_RIBBON'];
  function effectPose(plan, progress, style = 'AURORA_RIBBON') {
    if (!effectStyles.includes(style)) throw new RangeError('formation effect style');
    if (!Number.isFinite(progress) || progress < 0 || progress > 1) throw new RangeError('formation effect progress');
    const p = progress, opacity = smooth(p / .09) * (1 - smooth((p - .82) / .16));
    if (!opacity) return {style, opacity:0, particles:[], rings:[], rays:[]};
    const xs = plan.contour.map(v => v[0]), ys = plan.contour.map(v => v[1]);
    const rx = Math.max(...xs) - Math.min(...xs), ry = Math.max(...ys) - Math.min(...ys);
    const gather = smooth((p - .14) / .42), bloom = smooth((p - .56) / .25);
    const particles = Array.from({length:style === 'PETAL_BLOOM' ? 40 : 54}, (_, i) => {
      const {phase,route,target}=plan.effectSeeds[i];
      const vx = target[0] - plan.center[0], vy = target[1] - plan.center[1];
      const orbit = [plan.center[0] + Math.cos(phase + p * .7) * rx * (.51 + .07 * bloom),
        plan.center[1] + Math.sin(phase + p * .7) * ry * (.50 + .055 * bloom)];
      const destination = style === 'PETAL_BLOOM' ? [target[0] + vx * .12 * bloom, target[1] + vy * .12 * bloom] : orbit;
      const position = mix(route, destination, gather);
      position[0] += Math.sin(phase + p * 7) * .012 * Math.sin(gather * Math.PI);
      position[1] -= Math.sin(gather * Math.PI) * (.025 + (i % 4) * .006);
      return {position, size:(i % 9 === 0 ? .012 : .0046 + (i % 3) * .0013) * (.6 + .4 * Math.sin(Math.PI * p)),
        rotation:phase + p * (i % 2 ? 1.3 : -1.3), color:i % 5, alpha:opacity * (.42 + (i % 5) * .11),
        glint:i % 9 === 0, phase};
    });
    const axisRatio=Math.min(rx,ry)/Math.max(rx,ry);
    const rings = style === 'STARDUST' ? [
      {center:plan.center,rx:rx*.60,ry:ry*.55,rotation:-.18,start:-2.9+p*.3,end:-1.0+p*.3,alpha:opacity*gather*.45},
      {center:plan.center,rx:rx*.56,ry:ry*.51,rotation:.25,start:.2+p*.25,end:1.3+p*.25,alpha:opacity*gather*.25},
    ] : style === 'AURORA_RIBBON' ? [0,1,2].map(i => ({center:plan.center,rx:rx*(.54+i*.025),ry:ry*(.49+i*.025),rotation:(-.38+i*.2)*axisRatio,start:-Math.PI+p*1.4+i*.8,end:Math.PI*.45+p*1.4+i*.8,alpha:opacity*gather*(.65-i*.16)})) : [];
    const rays = style === 'PETAL_BLOOM' ? Array.from({length:10}, (_, i) => {
      const a = i * Math.PI / 5 + .2, spread = smooth((p - .52) / .22);
      return {from:[plan.center[0]+Math.cos(a)*rx*.46,plan.center[1]+Math.sin(a)*ry*.46],
        to:[plan.center[0]+Math.cos(a)*rx*(.46+spread*.22),plan.center[1]+Math.sin(a)*ry*(.46+spread*.22)],
        alpha:opacity*Math.sin(spread*Math.PI)*.48};
    }) : [];
    return {style, opacity, particles, rings, rays};
  }
  function drawEffects(ctx, plan, effect, layer) {
    if (!effect.opacity) return;
    const style=effect.style;
    const colors = ['#d7ad5f', plan.palette[0], '#a5b9d9', '#dfa48e', '#baa3d3'];
    ctx.save(); ctx.lineCap='round'; ctx.lineJoin='round';
    if(layer==='behind') {
      for(const [i,ring] of effect.rings.entries()){
        ctx.save();ctx.translate(...ring.center);ctx.rotate(ring.rotation);ctx.beginPath();ctx.ellipse(0,0,ring.rx,ring.ry,0,ring.start,ring.end);
        ctx.strokeStyle=rgba(colors[i%colors.length],ring.alpha);ctx.lineWidth=style==='AURORA_RIBBON'?.012:.002;ctx.stroke();
        if(style==='AURORA_RIBBON'){ctx.strokeStyle=rgba('#fff5d9',ring.alpha*.7);ctx.lineWidth=.002;ctx.stroke();}ctx.restore();
      }
      for(const ray of effect.rays){path(ctx,[ray.from,ray.to]);ctx.strokeStyle=rgba('#e5bc73',ray.alpha);ctx.lineWidth=.002;ctx.stroke();}
    }
    for(const particle of effect.particles){
      if((layer==='front')!==particle.glint)continue;
      ctx.save();ctx.translate(...particle.position);ctx.rotate(particle.rotation);ctx.globalAlpha=particle.alpha;ctx.fillStyle=colors[particle.color];
      const s=particle.size;
      if(style==='PETAL_BLOOM'){
        ctx.beginPath();ctx.moveTo(0,-s);ctx.bezierCurveTo(s*1.2,-s*.65,s*1.2,s*.8,0,s);ctx.bezierCurveTo(-s*.7,s*.5,-s*.6,-s*.5,0,-s);ctx.fill();
      }else if(particle.glint){
        ctx.beginPath();ctx.moveTo(0,-s);ctx.quadraticCurveTo(s*.16,-s*.16,s,0);ctx.quadraticCurveTo(s*.16,s*.16,0,s);ctx.quadraticCurveTo(-s*.16,s*.16,-s,0);ctx.quadraticCurveTo(-s*.16,-s*.16,0,-s);ctx.fill();
      }else{ctx.beginPath();ctx.arc(0,0,s*.6,0,Math.PI*2);ctx.fill();}
      ctx.restore();
    }
    ctx.restore();
  }
  function displayTransform(plan, width, height, fold) {
    const initial = Math.min(width * .82, height * 1.02);
    const xs = plan.contour.map(p => p[0]), ys = plan.contour.map(p => p[1]);
    const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
    // Fit the body, rather than transparent PNG margins. The same matrix applies to
    // its geometry, face and original image; the initial route still fits in full.
    const final = Math.min(width * .78 / (right - left), height * .76 / (bottom - top));
    const t = clamp(fold), scale = initial + (final - initial) * t;
    const start = [width / 2 - initial / 2, height * .46 - initial / 2];
    const end = [width / 2 - (left + right) / 2 * final, height * .46 - (top + bottom) / 2 * final];
    const [x, y] = mix(start, end, t);
    return { x, y, scale, bodyWidth: (right - left) * scale, bodyHeight: (bottom - top) * scale };
  }
  function createRenderer(image, plan, options = {}) {
    const effectStyle = options.effectStyle || 'AURORA_RIBBON';
    if(!effectStyles.includes(effectStyle))throw new RangeError('formation effect style');
    const size = image.naturalWidth, height = image.naturalHeight;
    const create = () => { const c = document.createElement('canvas'); c.width = size; c.height = height; return c; };
    const surface = create(), surfaceCtx = surface.getContext('2d');
    let faceMask, facePatch;
    if (plan.faceProtected) {
      faceMask = create(); facePatch = create();
      const maskCtx = faceMask.getContext('2d'), patchCtx = facePatch.getContext('2d');
      const [fx, fy] = plan.faceCenter, radius = .17 * size;
      const gradient = maskCtx.createRadialGradient(fx * size, fy * height, radius * .66, fx * size, fy * height, radius);
      gradient.addColorStop(0, '#fff'); gradient.addColorStop(1, 'rgba(255,255,255,0)');
      maskCtx.fillStyle = gradient; maskCtx.fillRect(0, 0, size, height);
      patchCtx.drawImage(image, 0, 0); patchCtx.globalCompositeOperation = 'destination-in'; patchCtx.drawImage(faceMask, 0, 0);
    }
    function paintBody(frame) {
      const ctx = surfaceCtx;
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.clearRect(0, 0, size, height);
      ctx.save(); ctx.scale(size, height);
      const xs = frame.contour.map(p => p[0]), ys = frame.contour.map(p => p[1]);
      const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys);
      if (frame.bodyOpacity > 0) {
        ctx.globalAlpha = frame.bodyOpacity;
        ctx.fillStyle = 'rgba(63,72,66,.075)'; ctx.beginPath();
        ctx.ellipse((left + right) / 2, bottom + .021, Math.max(.012, (right - left) * .32), .013, 0, 0, Math.PI * 2); ctx.fill();
        // A narrow lower surface supplies thickness; the filled body itself changes geometry.
        ctx.save(); ctx.translate(0, .004 * frame.inflate); path(ctx, frame.contour, true);
        ctx.fillStyle = rgba(plan.palette[1], .18); ctx.fill(); ctx.restore();
        path(ctx, frame.contour, true);
        ctx.fillStyle = tint(plan.palette[0], .14); ctx.fill();
        ctx.strokeStyle = rgba(plan.palette[1], .24); ctx.lineWidth = .002; ctx.lineJoin = 'round'; ctx.stroke();
        ctx.save(); path(ctx, frame.contour, true); ctx.clip();
        // Opaque illustrated color planes, not a glossy radial highlight.
        ctx.fillStyle = rgba(plan.palette[1], .12);
        ctx.fillRect(left, top + (bottom - top) * .72, right - left, bottom - top);
        ctx.restore();
      }
      ctx.restore();
      // Rigid translated face patch. Destination-out + lighter blends its source alpha once.
      if (frame.faceOpacity > 0) {
        const x = (frame.faceCenter[0] - plan.faceCenter[0]) * size, y = (frame.faceCenter[1] - plan.faceCenter[1]) * height;
        ctx.save(); ctx.globalAlpha = frame.faceOpacity; ctx.globalCompositeOperation = 'destination-out'; ctx.drawImage(faceMask, x, y);
        ctx.globalCompositeOperation = 'lighter'; ctx.drawImage(facePatch, x, y); ctx.restore();
      }
    }
    function draw(ctx, width, canvasHeight, progress, idle = 0) {
      const frame = pose(plan, progress), fit = displayTransform(plan, width, canvasHeight, frame.fold);
      const extent = fit.scale, dx = fit.x, dy = fit.y;
      const anchor = plan.faceCenter || plan.center;
      const cx = dx + anchor[0] * extent, cy = dy + anchor[1] * extent;
      if (progress === 1 && idle === 0) {
        // Draw the original once. An extra Canvas copy changes premultiplied edges
        // on Android and can make the still frame differ from the gently moving one.
        ctx.drawImage(image, dx, dy, extent, extent); return frame;
      }
      const celebration=effectPose(plan,progress,effectStyle);
      const paintEffects = layer => {
        ctx.save();ctx.translate(dx,dy);ctx.scale(extent,extent);
        if(plan.character && scope.NuntiJourneyEffects)scope.NuntiJourneyEffects.draw(ctx,plan,progress,layer);
        else drawEffects(ctx,plan,celebration,layer);
        ctx.restore();
      };
      paintEffects('behind');
      ctx.save(); ctx.translate(cx, cy + frame.floatY * extent + idle); ctx.scale(frame.scaleX, frame.scaleY); ctx.translate(-cx, -cy);
      if (frame.imageWeight === 1) {
        ctx.drawImage(image, dx, dy, extent, extent);
      } else {
        paintBody(frame);
        // Linear premultiplied crossfade only after contour has reached its exact final geometry.
        // This is a material hand-off following real growth, not a bitmap reveal as the growth itself.
        ctx.globalAlpha = 1 - frame.imageWeight; ctx.drawImage(surface, dx, dy, extent, extent);
        if (frame.imageWeight) { ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = frame.imageWeight; ctx.drawImage(image, dx, dy, extent, extent); }
      }
      ctx.restore();
      paintEffects('front');
      ctx.save(); ctx.translate(dx, dy); ctx.scale(extent, extent);
      if (frame.guideOpacity > 0) { path(ctx, plan.raw); ctx.strokeStyle = `rgba(99,137,112,${frame.guideOpacity})`; ctx.lineWidth = .002; ctx.lineCap = 'round'; ctx.stroke(); }
      if (frame.strokeOpacity > 0) {
        const stroke = trace(frame.centerline, frame.traceFraction); path(ctx, stroke);
        ctx.save();ctx.shadowColor=plan.character ? scope.NuntiJourneyEffects?.theme(plan).colors[0] || '#d6ac58' : '#d6ac58';ctx.shadowBlur=12;
        ctx.strokeStyle=`rgba(234,189,112,${frame.strokeOpacity*.38})`;ctx.lineWidth=.016;ctx.stroke();ctx.restore();
        ctx.strokeStyle = `rgba(207,165,91,${frame.strokeOpacity})`; ctx.lineWidth = .005; ctx.lineJoin = 'round'; ctx.lineCap = 'round'; ctx.stroke();
        const head = stroke.at(-1); ctx.beginPath(); ctx.arc(...head, .006, 0, Math.PI * 2); ctx.fillStyle = `rgba(255,231,177,${frame.strokeOpacity})`; ctx.fill();
      }
      ctx.restore();
      return frame;
    }
    return { draw, plan, effectStyle };
  }
  const api = { prepare, pose, trace, resample, atArc, area, displayTransform, createRenderer, effectPose, effectStyles };
  scope.NuntiFormation = api;
  if (typeof module !== 'undefined') module.exports = api;
})(globalThis);
