(() => {
  const root = document.getElementById('__ROOT_ID__');
  const dataNode = document.getElementById('__DATA_ID__');
  if (!root || !dataNode) return;
  const spec = JSON.parse(dataNode.textContent);
  const choices = new Map((spec.presentation.options || []).map((item) => [item.id, item]));
  let selectedId = spec.presentation.recommendation?.option_id || spec.presentation.options?.[0]?.id || null;
  const status = root.querySelector('[data-dc-status]');
  const detailName = root.querySelector('[data-dc-detail-name]');
  const detailSummary = root.querySelector('[data-dc-detail-summary]');
  const detailTradeoff = root.querySelector('[data-dc-detail-tradeoff]');
  const storyCurve = root.querySelector('[data-dc-story-curve]');
  const curveField = (spec.presentation.fields || []).find((item) => item.id === 'story_curve');
  const curveData = curveField?.value;
  let focusedSeriesId = curveData?.series?.[0]?.id || null;
  const shotRhythm = root.querySelector('[data-dc-shot-rhythm]');
  const shotRhythmField = (spec.presentation.fields || []).find((item) => item.id === 'shot_rhythm');
  const shotRhythmData = shotRhythmField?.value;
  let focusedShotId = shotRhythmData?.shots?.[0]?.id || null;
  const assetGraphStage = root.querySelector('[data-dc-graph-stage]');
  const assetGraphSvg = root.querySelector('[data-dc-graph-edges]');
  const assetGraphField = (spec.presentation.fields || []).find((item) => item.id === 'asset_graph');
  const assetGraphData = assetGraphField?.value;
  let focusedGraphNodeId = assetGraphData?.nodes?.find((item) => item.type === 'asset')?.id || assetGraphData?.nodes?.[0]?.id || null;
  const qaDeltaField = (spec.presentation.fields || []).find((item) => item.id === 'qa_delta');
  const qaDeltaData = qaDeltaField?.value;
  const visualBoardField = (spec.presentation.fields || []).find((item) => item.id === 'visual_board');
  const visualBoardData = visualBoardField?.value;

  function svgNode(name, attributes = {}, text = '') {
    const node = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text) node.textContent = text;
    return node;
  }

  const spatial = spec.spatial_render;
  const cameraSelect = root.querySelector('[data-dc-spatial-camera]');
  const phaseSelect = root.querySelector('[data-dc-spatial-phase]');
  let currentSpatialView = null;
  if (spatial) {
    const colors = new Map((spatial.colors || []).map((e) => [e.color, e.color]));
    const legend = root.querySelector('[data-dc-spatial-legend]');
    const shortLabel = (label, max = 10) => String(label || '').length > max ? `${String(label).slice(0, max - 1)}…` : String(label || '');
    const statesFor = (view) => view.entity_states || spec.presentation.spatial_scene?.entities?.map((entity) => ({...entity, position: view.entity_positions?.[entity.id]})) || (spatial.colors || []).map((entity) => ({...entity, position: view.entity_positions?.[entity.id]}));
    const actorCode = (view, entity) => {
      if (entity.marker_id) return entity.marker_id;
      const actors = statesFor(view).filter((item) => item.kind !== 'prop' && item.visible !== false);
      const index = actors.findIndex((item) => item.id === entity.id);
      return index >= 0 && index < 26 ? String.fromCharCode(65 + index) : entity.id.slice(0, 2);
    };
    const isAtEntity = (view, point) => statesFor(view).some((entity) => entity.position && Math.hypot(entity.position[0] - point[0], entity.position[1] - point[1]) < .03);

    function marker(defs, id, color) {
      const node = svgNode('marker', {id, viewBox: '0 0 8 8', refX: 6.5, refY: 4, markerWidth: 6, markerHeight: 6, orient: 'auto'});
      node.append(svgNode('path', {d: 'M 0 0 L 8 4 L 0 8 z', fill: color}));
      defs.append(node);
    }
    function updateLegend(view) {
      if (!legend) return;
      legend.replaceChildren();
      statesFor(view).filter((entity) => entity.visible !== false).forEach((entity) => {
        const mark = document.createElement('span');
        mark.style.color = colors.get(entity.color) || entity.color || 'var(--foreground, #1f2937)';
        mark.textContent = entity.kind === 'prop' ? '◆ ' : '● ';
        mark.setAttribute('aria-hidden', 'true');
        const item = document.createElement('span');
        const hand = entity.holder_hand ? `${entity.holder_hand === 'left' ? '左' : '右'}手` : '持有';
        const holder = statesFor(view).find((candidate) => candidate.id === entity.holder);
        const actor = entity.kind === 'prop' ? '' : `${actorCode(view, entity)} · `;
        item.append(mark, document.createTextNode(`${actor}${shortLabel(entity.label || entity.id)}${entity.kind === 'prop' && entity.holder ? ` · ${shortLabel(entity.holder_label || holder?.label || entity.holder)}${hand}` : ''}`));
        legend.append(item);
      });
    }
    function drawFloorplan(svg, view) {
      if (!svg) return;
      const width = Math.max(280, Math.round(svg.getBoundingClientRect().width));
      const height = Math.max(240, Math.round(width * .66));
      const margin = 22;
      const px = (p) => [margin + p[0] * (width - margin * 2), margin + p[1] * (height - margin * 2)];
      svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('height', height); svg.replaceChildren();
      const defs = svgNode('defs'); marker(defs, `${root.id}-motion-arrow`, 'var(--foreground, #1f2937)'); svg.append(defs);
      const group = svgNode('g'); const featureLabels = [];
      const sourceFeatures = (spec.presentation.spatial_scene?.room?.features || []).map((feature) => ({points: [[feature.position[0]-feature.size[0]/2, feature.position[1]-feature.size[1]/2], [feature.position[0]+feature.size[0]/2, feature.position[1]-feature.size[1]/2], [feature.position[0]+feature.size[0]/2, feature.position[1]+feature.size[1]/2], [feature.position[0]-feature.size[0]/2, feature.position[1]+feature.size[1]/2]], closed: true, label: feature.label, dashed: ['inferred', 'unseen'].includes(feature.evidence)}));
      const shapes = (view.top || []).some((shape) => shape.label) ? view.top || [] : sourceFeatures;
      shapes.filter((shape) => !shape.entity_id && shape.color !== 'camera' && shape.closed).forEach((shape) => {
        const points = shape.points.map(px); group.append(svgNode('polygon', {points: points.map((p) => p.join(',')).join(' '), stroke: 'var(--border)', fill: 'color-mix(in srgb, var(--muted) 18%, transparent)', 'stroke-width': 1.4, ...(shape.dashed ? {'stroke-dasharray': '5 4', 'data-dc-floor-inferred': 'true'} : {})}));
        if (shape.label) { const center = points.reduce((total, point) => [total[0] + point[0] / points.length, total[1] + point[1] / points.length], [0, 0]); const top = Math.min(...points.map((point) => point[1])); const label = svgNode('text', {x: center[0], y: Math.max(14, top + 12), 'text-anchor': 'middle', fill: 'var(--foreground)', 'font-size': 12, 'font-weight': 500, 'data-dc-floor-label': 'feature'}, shortLabel(shape.label, 8)); group.append(label); featureLabels.push({label, points}); }
      });
      shapes.filter((shape) => shape.dashed && !shape.closed && shape.color !== 'camera').forEach((shape) => {
        const points = shape.points.map(px); const isEyeline = shape.points.length === 2 && isAtEntity(view, shape.points.at(-1)); const color = colors.get(shape.color) || 'var(--muted-foreground, #64748b)';
        group.append(svgNode('polyline', {points: points.map((p) => p.join(',')).join(' '), stroke: color, fill: 'none', 'stroke-width': isEyeline ? 1 : 2.2, opacity: isEyeline ? .45 : 1, ...(isEyeline ? {'stroke-dasharray': '3 4'} : {'marker-end': `url(#${root.id}-motion-arrow)`, 'data-dc-floor-motion': 'true'})}));
        if (!isEyeline) group.append(svgNode('circle', {cx: points[0][0], cy: points[0][1], r: 4, fill: 'var(--background)', stroke: color, 'stroke-width': 1.5, 'data-dc-floor-motion-start': 'true'}));
      });
      const camera = shapes.find((shape) => shape.color === 'camera');
      const cameraSpec = (spec.presentation.spatial_scene?.cameras || []).find((candidate) => candidate.shot_id === view.shot_id);
      if (camera) { const points = camera.points.map(px); const center = [(points[0][0] + points[1][0]) / 2, (points[0][1] + points[1][1]) / 2]; const target = points[2]; const dx = target[0] - center[0], dy = target[1] - center[1], distance = Math.hypot(dx, dy) || 1, spread = distance * Math.tan((cameraSpec?.hfov_deg || 45) * Math.PI / 360), right = [-dy / distance * spread, dx / distance * spread]; const fov = [center, [target[0] + right[0], target[1] + right[1]], [target[0] - right[0], target[1] - right[1]]]; group.append(svgNode('polygon', {points: fov.map((point) => point.join(',')).join(' '), fill: 'color-mix(in srgb, var(--foreground) 10%, transparent)', stroke: 'var(--foreground)', 'stroke-width': 1.5, 'data-dc-floor-camera': 'true'})); group.append(svgNode('circle', {cx: center[0], cy: center[1], r: 10, fill: 'var(--background)', stroke: 'var(--foreground)', 'stroke-width': 2, 'data-dc-floor-camera-marker': 'true'})); group.append(svgNode('text', {x: center[0], y: center[1] + 4, 'text-anchor': 'middle', fill: 'var(--foreground)', 'font-size': 11, 'font-weight': 500, 'data-dc-floor-label': 'camera'}, `C${Math.max(1, (spatial.views || []).filter((item) => item.phase === view.phase).findIndex((item) => item.shot_id === view.shot_id) + 1)}`)); }
      statesFor(view).filter((entity) => entity.kind !== 'prop' && entity.visible !== false && entity.position).forEach((entity) => {
        const [x, y] = px(entity.position); const color = colors.get(entity.color) || entity.color || 'var(--foreground, #1f2937)'; group.append(svgNode('circle', {cx: x, cy: y, r: 13, fill: color, stroke: 'var(--background, #fff)', 'stroke-width': 2.5, 'data-dc-floor-entity': entity.id})); group.append(svgNode('text', {x, y: y + 4, 'text-anchor': 'middle', fill: 'white', 'font-size': 11, 'font-weight': 700}, actorCode(view, entity)));
        if (Array.isArray(entity.facing) && Math.hypot(entity.facing[0], entity.facing[1]) > .001) { const magnitude = Math.hypot(entity.facing[0], entity.facing[1]); const ux = entity.facing[0] / magnitude, uy = entity.facing[1] / magnitude; group.append(svgNode('line', {x1: x + ux * 15, y1: y + uy * 15, x2: x + ux * 29, y2: y + uy * 29, stroke: 'white', 'stroke-width': 2.5, 'marker-end': `url(#${root.id}-motion-arrow)`, 'data-dc-floor-facing': 'true'})); }
      });
      statesFor(view).filter((entity) => entity.kind === 'prop' && entity.visible !== false && entity.position).forEach((entity) => { const [x, y] = px(entity.position); const color = colors.get(entity.color) || entity.color || 'var(--foreground, #1f2937)'; group.append(svgNode('path', {d: `M ${x} ${y - 7} L ${x + 7} ${y} L ${x} ${y + 7} L ${x - 7} ${y} Z`, fill: color, stroke: 'var(--background, #fff)', 'stroke-width': 2, 'data-dc-floor-prop': entity.id})); });
      svg.append(group);
      const overlaps = (a, b) => Math.min(a.x+a.width, b.x+b.width) - Math.max(a.x,b.x) > 1 && Math.min(a.y+a.height, b.y+b.height) - Math.max(a.y,b.y) > 1;
      const blockers = [...svg.querySelectorAll('[data-dc-floor-entity], [data-dc-floor-facing], [data-dc-floor-prop], [data-dc-floor-motion], [data-dc-floor-camera-marker], [data-dc-floor-label="camera"]')];
      featureLabels.forEach(({label, points}) => {
        const center = points.reduce((total, point) => [total[0] + point[0] / points.length, total[1] + point[1] / points.length], [0, 0]); const minX = Math.min(...points.map((point) => point[0])), maxX = Math.max(...points.map((point) => point[0])), minY = Math.min(...points.map((point) => point[1])), maxY = Math.max(...points.map((point) => point[1]));
        const choices = [[center[0], Math.max(14, minY + 12), 'middle'], [center[0], Math.min(height - 4, maxY + 14), 'middle'], [Math.max(4, minX - 4), center[1] + 4, 'end'], [Math.min(width - 4, maxX + 4), center[1] + 4, 'start'], [Math.max(4, minX - 4), Math.max(14, minY - 5), 'end'], [Math.min(width - 4, maxX + 4), Math.max(14, minY - 5), 'start'], [Math.max(4, minX - 4), Math.min(height - 4, maxY + 14), 'end'], [Math.min(width - 4, maxX + 4), Math.min(height - 4, maxY + 14), 'start']];
        for (const [x, y, anchor] of choices) { label.setAttribute('x', x); label.setAttribute('y', y); label.setAttribute('text-anchor', anchor); const box = label.getBBox(); if (box.x >= 0 && box.y >= 0 && box.x + box.width <= width && box.y + box.height <= height && !blockers.some((node) => overlaps(box, node.getBBox()))) break; }
      });
    }
    function drawProjection(svg, shapes) {
      if (!svg || !shapes?.length) return;
      const width = Math.max(240, Math.round(svg.getBoundingClientRect().width)); const height = width * 9 / 16; const px = (p) => [p[0] * width, p[1] * height]; svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.setAttribute('height', height); svg.replaceChildren();
      shapes.forEach((shape) => svg.append(svgNode(shape.closed ? 'polygon' : 'polyline', {points: shape.points.map(px).map((p) => p.join(',')).join(' '), stroke: colors.get(shape.color) || 'var(--foreground)', fill: shape.fill ? 'var(--background)' : 'none', 'stroke-width': shape.entity_id ? 1.6 : 1, ...(shape.entity_id ? {'data-entity-id': shape.entity_id} : {})}))); svg.append(svgNode('rect', {x: .5, y: .5, width: width - 1, height: height - 1, fill: 'none', stroke: 'var(--border)'}));
    }
    function candidateView() { const phase = phaseSelect?.value || 'initial'; if (cameraSelect) return spatial.views.find((view) => view.shot_id === cameraSelect.value && view.phase === phase); return spatial.overview?.find?.((view) => view.phase === phase) || spatial.overview || spatial.views?.find((view) => view.phase === phase) || spatial.views?.[0]; }
    function drawSpatial() { currentSpatialView = candidateView(); if (!currentSpatialView) return; root.dataset.spatialShot = currentSpatialView.shot_id || 'overview'; root.dataset.spatialPhase = currentSpatialView.phase || 'initial'; drawFloorplan(root.querySelector('[data-dc-spatial-top]'), currentSpatialView); drawProjection(root.querySelector('[data-dc-spatial-frame]'), currentSpatialView.frame); updateLegend(currentSpatialView); const detail = root.querySelector('[data-dc-spatial-detail]'); if (detail) detail.textContent = `${currentSpatialView.label || '俯视讨论'}${cameraSelect ? ' · FOV 为设计示意' : ''}`; }
    cameraSelect?.addEventListener('change', drawSpatial); phaseSelect?.addEventListener('change', drawSpatial); new ResizeObserver(drawSpatial).observe(root); drawSpatial();
  }

  function drawStoryCurve() {
    if (!storyCurve || !curveData || !Array.isArray(curveData.series)) return;
    const width = Math.max(280, Math.round(storyCurve.getBoundingClientRect().width));
    const height = width <= 420 ? 280 : 256;
    const margin = { top: 34, right: 14, bottom: 34, left: 38 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const x = (time) => margin.left + (Number(time) / Number(curveData.duration)) * plotWidth;
    const y = (value) => margin.top + (1 - Number(value) / 100) * plotHeight;
    storyCurve.setAttribute('viewBox', `0 0 ${width} ${height}`);
    storyCurve.replaceChildren();
    storyCurve.append(svgNode('title', {}, curveData.summary || '故事曲线'));
    storyCurve.append(svgNode('desc', {}, '横轴为秒，纵轴为相对强度零到一百。'));

    [0, 50, 100].forEach((value) => {
      storyCurve.append(svgNode('line', { class: 'dc-curve-grid', x1: margin.left, y1: y(value), x2: width - margin.right, y2: y(value) }));
      storyCurve.append(svgNode('text', { class: 'dc-curve-label', x: margin.left - 7, y: y(value) + 4, 'text-anchor': 'end' }, String(value)));
    });
    [0, curveData.duration / 2, curveData.duration].forEach((value, index) => {
      const anchor = index === 0 ? 'start' : index === 2 ? 'end' : 'middle';
      const timeLabel = Number.isInteger(value) ? String(value) : Number(value).toFixed(1);
      storyCurve.append(svgNode('text', { class: 'dc-curve-label', x: x(value), y: height - 8, 'text-anchor': anchor }, `${timeLabel}s`));
    });
    storyCurve.append(svgNode('text', { class: 'dc-curve-label', x: margin.left, y: 14 }, '相对强度'));

    (curveData.annotations || []).slice(0, 5).forEach((annotation, index) => {
      const annotationX = x(annotation.time);
      storyCurve.append(svgNode('line', { class: 'dc-curve-annotation', x1: annotationX, y1: margin.top, x2: annotationX, y2: height - margin.bottom }));
      const anchor = annotationX < margin.left + 45 ? 'start' : annotationX > width - margin.right - 45 ? 'end' : 'middle';
      storyCurve.append(svgNode('text', { class: 'dc-curve-marker', x: annotationX, y: margin.top + 16, 'text-anchor': anchor }, String(index + 1)));
    });

    curveData.series.forEach((series, index) => {
      const points = series.points.map((point) => `${x(point.time)},${y(point.value)}`).join(' ');
      const classes = ['dc-curve-path', `dc-series-${index + 1}`];
      if (focusedSeriesId && focusedSeriesId !== series.id) classes.push('is-dimmed');
      if (focusedSeriesId === series.id) classes.push('is-focused');
      const path = svgNode('polyline', { class: classes.join(' '), points, 'data-dc-curve-path': series.id });
      storyCurve.append(path);
      series.points.forEach((point) => {
        const pointClasses = ['dc-curve-point', `dc-series-${index + 1}`];
        if (focusedSeriesId && focusedSeriesId !== series.id) pointClasses.push('is-dimmed');
        storyCurve.append(svgNode('circle', {
          class: pointClasses.join(' '),
          cx: x(point.time), cy: y(point.value), r: focusedSeriesId === series.id ? 3 : 2,
          fill: 'currentColor', 'aria-hidden': 'true',
        }));
      });
    });
  }

  function focusCurveSeries(seriesId) {
    if (!curveData?.series?.some((item) => item.id === seriesId)) return;
    focusedSeriesId = seriesId;
    root.querySelectorAll('[data-dc-curve-series]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.dcCurveSeries === seriesId));
    });
    const selectedSeries = curveData.series.find((item) => item.id === seriesId);
    const insight = root.querySelector('[data-dc-curve-insight]');
    if (insight) insight.textContent = selectedSeries.insight;
    drawStoryCurve();
  }

  root.querySelectorAll('[data-dc-curve-series]').forEach((button) => {
    button.addEventListener('click', () => focusCurveSeries(button.dataset.dcCurveSeries));
  });
  if (storyCurve) {
    drawStoryCurve();
    window.addEventListener('resize', drawStoryCurve, { passive: true });
  }

  function shotLaneValue(shot, laneId) {
    if (laneId === 'shot') return shot.id.toUpperCase();
    return shot[laneId] || '';
  }

  function drawShotRhythm() {
    if (!shotRhythm || !shotRhythmData || !Array.isArray(shotRhythmData.shots)) return;
    const width = Math.max(560, Math.round(shotRhythm.getBoundingClientRect().width));
    const lanes = [
      ['shot', '镜头'], ['size', '景别'], ['movement', '运动'],
      ['action', '动作'], ['audio', '声音'], ['risk', '风险'],
    ];
    const margin = { top: 28, right: 8, bottom: 26, left: 58 };
    const laneHeight = 34;
    const height = margin.top + lanes.length * laneHeight + margin.bottom;
    const plotWidth = width - margin.left - margin.right;
    const x = (time) => margin.left + (Number(time) / Number(shotRhythmData.duration)) * plotWidth;
    shotRhythm.setAttribute('viewBox', `0 0 ${width} ${height}`);
    shotRhythm.replaceChildren();
    shotRhythm.append(svgNode('title', {}, shotRhythmData.summary || '镜头节奏'));
    shotRhythm.append(svgNode('desc', {}, '所有轨道共享同一时间轴，依次显示镜头、景别、运动、动作、声音和风险。'));

    [0, shotRhythmData.duration / 2, shotRhythmData.duration].forEach((value, index) => {
      const tickX = x(value);
      const anchor = index === 0 ? 'start' : index === 2 ? 'end' : 'middle';
      shotRhythm.append(svgNode('line', { class: 'dc-shot-grid', x1: tickX, y1: margin.top - 5, x2: tickX, y2: height - margin.bottom }));
      const timeLabel = Number.isInteger(value) ? String(value) : Number(value).toFixed(1);
      shotRhythm.append(svgNode('text', { class: 'dc-shot-axis-label', x: tickX, y: 16, 'text-anchor': anchor }, `${timeLabel}s`));
    });

    lanes.forEach(([laneId, laneLabel], laneIndex) => {
      const laneY = margin.top + laneIndex * laneHeight;
      shotRhythm.append(svgNode('text', { class: 'dc-shot-row-label', x: margin.left - 8, y: laneY + 22, 'text-anchor': 'end' }, laneLabel));
      shotRhythm.append(svgNode('line', { class: 'dc-shot-row-line', x1: margin.left, y1: laneY + laneHeight - 1, x2: width - margin.right, y2: laneY + laneHeight - 1 }));
      shotRhythmData.shots.forEach((shot) => {
        const bandX = x(shot.start);
        const bandWidth = Math.max(2, x(shot.end) - bandX);
        const selected = shot.id === focusedShotId;
        shotRhythm.append(svgNode('rect', {
          class: `dc-shot-band${selected ? ' is-selected' : ''}`,
          x: bandX + 1, y: laneY + 4, width: Math.max(1, bandWidth - 2), height: laneHeight - 9,
          rx: 3, 'data-dc-shot-band': shot.id,
        }));
        const value = String(shotLaneValue(shot, laneId));
        const maxChars = Math.floor((bandWidth - 8) / 8);
        if (maxChars >= 2) {
          const label = value.length > maxChars ? `${value.slice(0, Math.max(1, maxChars - 1))}…` : value;
          shotRhythm.append(svgNode('text', {
            class: `dc-shot-band-label${selected ? ' is-selected' : ''}`,
            x: bandX + bandWidth / 2, y: laneY + 22, 'text-anchor': 'middle', 'aria-hidden': 'true',
          }, label));
        }
      });
    });
  }

  function focusShot(shotId) {
    const shot = shotRhythmData?.shots?.find((item) => item.id === shotId);
    if (!shot) return;
    focusedShotId = shotId;
    root.querySelectorAll('[data-dc-shot]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.dcShot === shotId));
    });
    root.querySelectorAll('[data-dc-shot-mobile]').forEach((row) => {
      row.classList.toggle('is-selected', row.dataset.dcShotMobile === shotId);
    });
    const detail = root.querySelector('[data-dc-shot-detail]');
    if (detail) {
      detail.textContent = `${shot.id.toUpperCase()} ${shot.start}–${shot.end}s · ${shot.size}/${shot.movement} · ${shot.label} · 风险：${shot.risk}`;
    }
    drawShotRhythm();
  }

  root.querySelectorAll('[data-dc-shot]').forEach((button) => {
    button.addEventListener('click', () => focusShot(button.dataset.dcShot));
  });
  if (shotRhythm) {
    drawShotRhythm();
    window.addEventListener('resize', drawShotRhythm, { passive: true });
  }

  function drawAssetGraph() {
    if (!assetGraphStage || !assetGraphSvg || !assetGraphData) return;
    const stageRect = assetGraphStage.getBoundingClientRect();
    if (!stageRect.width || !stageRect.height) return;
    assetGraphSvg.setAttribute('viewBox', `0 0 ${stageRect.width} ${stageRect.height}`);
    assetGraphSvg.replaceChildren();
    assetGraphSvg.append(svgNode('title', {}, assetGraphData.summary || '参考素材关系'));
    assetGraphData.edges.forEach((edge) => {
      const source = root.querySelector(`[data-dc-graph-node="${edge.source}"]`);
      const target = root.querySelector(`[data-dc-graph-node="${edge.target}"]`);
      if (!source || !target) return;
      const sourceRect = source.getBoundingClientRect();
      const targetRect = target.getBoundingClientRect();
      const sourceIsLeft = sourceRect.left < targetRect.left;
      const x1 = (sourceIsLeft ? sourceRect.right : sourceRect.left) - stageRect.left;
      const x2 = (sourceIsLeft ? targetRect.left : targetRect.right) - stageRect.left;
      const y1 = sourceRect.top - stageRect.top + sourceRect.height / 2;
      const y2 = targetRect.top - stageRect.top + targetRect.height / 2;
      const middle = (x1 + x2) / 2;
      const incident = edge.source === focusedGraphNodeId || edge.target === focusedGraphNodeId;
      const classes = ['dc-graph-edge', `is-${edge.kind}`];
      if (incident) classes.push('is-highlighted');
      else classes.push('is-dimmed');
      assetGraphSvg.append(svgNode('path', {
        class: classes.join(' '),
        d: `M ${x1} ${y1} C ${middle} ${y1}, ${middle} ${y2}, ${x2} ${y2}`,
        'data-dc-graph-edge': edge.id,
      }));
    });
  }

  function focusGraphNode(nodeId) {
    const node = assetGraphData?.nodes?.find((item) => item.id === nodeId);
    if (!node) return;
    focusedGraphNodeId = nodeId;
    root.querySelectorAll('[data-dc-graph-node]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.dcGraphNode === nodeId));
    });
    const connectedEdges = assetGraphData.edges.filter((edge) => edge.source === nodeId || edge.target === nodeId);
    const connectedLabels = connectedEdges.map((edge) => {
      const otherId = edge.source === nodeId ? edge.target : edge.source;
      return assetGraphData.nodes.find((item) => item.id === otherId)?.label || otherId;
    });
    const detail = root.querySelector('[data-dc-graph-detail]');
    if (detail) {
      const relationship = node.type === 'asset' ? '关联镜头' : '使用素材';
      detail.textContent = `${node.label}：${node.detail}；${relationship} ${connectedLabels.join('、') || '无'}。`;
    }
    drawAssetGraph();
  }

  root.querySelectorAll('[data-dc-graph-node]').forEach((button) => {
    button.addEventListener('click', () => focusGraphNode(button.dataset.dcGraphNode));
  });
  if (assetGraphStage) {
    drawAssetGraph();
    window.addEventListener('resize', drawAssetGraph, { passive: true });
  }

  function focusQaCandidate(candidateId) {
    const candidate = qaDeltaData?.candidates?.find((item) => item.id === candidateId);
    if (!candidate) return;
    root.querySelectorAll('[data-dc-qa-column]').forEach((cell) => {
      cell.classList.toggle('is-selected', cell.dataset.dcQaColumn === candidateId);
    });
    root.querySelectorAll('[data-dc-image-preview]').forEach((preview) => {
      const selected = preview.dataset.dcImagePreview === candidateId;
      preview.hidden = !selected;
      preview.classList.toggle('is-selected', selected);
    });
    const bindings = {
      '[data-dc-qa-judgment]': candidate.judgment,
      '[data-dc-qa-blocker]': candidate.blocker,
      '[data-dc-qa-retry]': candidate.retry,
      '[data-dc-qa-preserve]': candidate.preserve,
    };
    Object.entries(bindings).forEach(([selector, value]) => {
      const node = root.querySelector(selector);
      if (node) node.textContent = value;
    });
    const primaryAction = root.querySelector('.btn-primary[data-dc-action]');
    if (primaryAction) primaryAction.textContent = candidate.action_label;
  }

  root.querySelectorAll('[data-dc-qa-candidate]').forEach((button) => {
    button.addEventListener('click', () => focusQaCandidate(button.dataset.dcQaCandidate));
  });

  function replaceBoardTokens(selector, values) {
    const container = root.querySelector(selector);
    if (!container) return;
    const tokens = values.map((value) => {
      const token = document.createElement('span');
      token.className = 'viz-badge';
      token.textContent = value;
      return token;
    });
    container.replaceChildren(...tokens);
  }

  function focusBoardDirection(directionId) {
    const direction = visualBoardData?.directions?.find((item) => item.id === directionId);
    if (!direction) return;
    const palette = root.querySelector('[data-dc-board-palette]');
    if (palette) {
      const swatches = direction.palette.map((color) => {
        const item = document.createElement('span');
        item.className = 'dc-swatch-item';
        const swatch = document.createElement('span');
        swatch.className = 'dc-swatch';
        swatch.style.setProperty('--dc-swatch', color.color);
        swatch.setAttribute('aria-hidden', 'true');
        const label = document.createElement('span');
        label.className = 'text-small';
        label.textContent = color.label;
        item.append(swatch, label);
        return item;
      });
      palette.replaceChildren(...swatches);
    }
    const bindings = {
      '[data-dc-board-lighting]': direction.lighting,
      '[data-dc-board-judgment]': direction.judgment,
      '[data-dc-board-impact]': direction.impact,
    };
    Object.entries(bindings).forEach(([selector, value]) => {
      const node = root.querySelector(selector);
      if (node) node.textContent = value;
    });
    replaceBoardTokens('[data-dc-board-materials]', direction.materials);
    replaceBoardTokens('[data-dc-board-optics]', direction.optics);
    replaceBoardTokens('[data-dc-board-allow]', direction.allow);
    replaceBoardTokens('[data-dc-board-avoid]', direction.avoid);
  }

  root.querySelectorAll('[data-dc-board-direction]').forEach((button) => {
    button.addEventListener('click', () => focusBoardDirection(button.dataset.dcBoardDirection));
  });

  function renderChoice(choiceId) {
    if (!choices.has(choiceId)) return;
    selectedId = choiceId;
    const choice = choices.get(choiceId);
    root.querySelectorAll('[data-dc-choice]').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.dcChoice === choiceId));
    });
    if (detailName) detailName.textContent = choice.label;
    if (detailSummary) detailSummary.textContent = choice.summary;
    if (detailTradeoff) detailTradeoff.textContent = choice.tradeoff;
    const details = new Map((choice.details || []).map((item) => [item.id, item]));
    root.querySelectorAll('[data-dc-detail-row]').forEach((row) => {
      const detail = details.get(row.dataset.dcDetailRow);
      row.hidden = !detail;
      if (detail) {
        const value = row.querySelector('[data-dc-detail-value]');
        if (value) value.textContent = detail.value;
      }
    });
    if (status) status.textContent = `已选择“${choice.label}”；发送后才会确认。`;
  }

  root.querySelectorAll('[data-dc-choice]').forEach((button) => {
    button.addEventListener('click', () => renderChoice(button.dataset.dcChoice));
  });

  root.querySelectorAll('[data-dc-action]').forEach((button) => {
    button.addEventListener('click', async () => {
      const action = spec.interactions.actions.find((item) => item.id === button.dataset.dcAction);
      if (!action) return;
      const selected = selectedId ? choices.get(selectedId) : null;
      const selection = selected ? ` 当前暂存选择：${selected.label}。` : '';
      const selectedQaCandidate = qaDeltaData?.candidates?.find((item) => item.id === selectedId);
      const conversationIntent = action.kind === 'retry_smallest' && selectedQaCandidate
        ? selectedQaCandidate.conversation_intent
        : action.conversation_intent;
      const followUpTitle = selectedQaCandidate?.action_label || action.label;
      const phaseLabel = currentSpatialView?.phase === 'initial' ? '起始' : currentSpatialView?.phase === 'final' ? '结束' : `第 ${currentSpatialView?.phase.split('-')[1]} 次${currentSpatialView?.phase.startsWith('transfer-') ? '交接' : '走位'}后`;
      const spatialSelection = currentSpatialView ? ` 场景 ${spatial.scene_id}，修订 ${spatial.revision}，机位 ${currentSpatialView.shot_id}，${phaseLabel}状态。` : '';
      const prompt = spec.interaction_mode && spec.interaction_mode !== 'decision'
        ? `${conversationIntent}${spatialSelection}${selection}`
        : `${conversationIntent}${selection} 当前阶段：${spec.view.customer_stage_label}。请先重新核对当前项目记录和进度，再用用户能理解的语言说明：确认了什么、哪些内容继续沿用、哪些内容需要重看、接下来会看到什么。确认无冲突后再记录，并给出简洁确认。`;
      if (window.openai && typeof window.openai.sendFollowUpMessage === 'function') {
        try {
          await window.openai.sendFollowUpMessage({ prompt, title: followUpTitle });
          if (status) status.textContent = '请求已发送。';
        } catch (error) {
          if (status) status.textContent = `请求未发送，请在对话中输入：${prompt}`;
        }
      } else if (status) {
        status.textContent = `当前表面不支持对话提交；请在聊天中输入：${prompt}`;
      }
    });
  });
})();
