#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { pathToFileURL } = require('url');
const { chromium } = require('playwright');

function argument(name, fallback) {
  const index = process.argv.indexOf(name);
  return index >= 0 && process.argv[index + 1] ? process.argv[index + 1] : fallback;
}

async function auditPage(browser, pageSpec, outputDir, viewport, theme, mode = 'default') {
  const page = await browser.newPage({ viewport: { width: viewport, height: 900 }, colorScheme: theme });
  const errors = [];
  page.on('console', (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  });
  page.on('pageerror', (error) => errors.push(`pageerror: ${error.message}`));
  await page.addInitScript(() => {
    window.__dcFollowUps = [];
    window.openai = {
      sendFollowUpMessage: async (payload) => {
        window.__dcFollowUps.push(payload);
      },
    };
  });
  await page.goto(pathToFileURL(pageSpec.page).href, { waitUntil: 'load' });
  if (mode === 'text-spacing') {
    await page.addStyleTag({ content: `
      [data-dircreative-visual], [data-dircreative-visual] * {
        line-height: 1.5 !important;
        letter-spacing: 0.12em !important;
        word-spacing: 0.16em !important;
      }
    ` });
  } else if (mode === 'large-text') {
    await page.addStyleTag({ content: `
      [data-dircreative-visual] { font-size: 1.5rem !important; }
    ` });
  }
  const root = page.locator('[data-dircreative-visual]');
  if (await root.count() !== 1) errors.push('expected exactly one visualization root');
  const actionCount = await page.locator('[data-dc-action]').count();
  if (pageSpec.surface_kind === 'confirmation') {
    if (actionCount !== 0) errors.push(`confirmation action count ${actionCount} must be 0`);
    const echoRows = await page.locator('.dc-echo-row').count();
    if (echoRows < 5) errors.push(`confirmation echo rows ${echoRows} < 5`);
  } else if (actionCount < 1 || actionCount > 2) {
    errors.push(`action count ${actionCount} outside 1..2`);
  }

  const choiceCount = await page.locator('[data-dc-choice]').count();
  if (choiceCount > 1) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const previews = spec.presentation.previews || [];
    if (pageSpec.name === 'generation-qa-no-media') {
      if (previews.length !== 0) errors.push('no-media QA unexpectedly contains previews');
      if (await page.locator('[data-dc-image-preview]').count()) errors.push('no-media QA rendered an image preview');
      const mediaStatus = (await page.locator('.dc-qa-media-status').textContent() || '').trim();
      if (!mediaStatus.includes('没有可显示的媒体')) errors.push('no-media QA missing explicit media fallback status');
    }
    if (previews.length) {
      const imageState = await page.locator('[data-dc-image-preview] img').evaluateAll((images) => images.map((image) => ({
        complete: image.complete,
        naturalWidth: image.naturalWidth,
        alt: image.getAttribute('alt') || '',
        source: image.getAttribute('src') || '',
      })));
      if (imageState.length !== previews.length) errors.push(`image preview count ${imageState.length} != ${previews.length}`);
      imageState.forEach((image, index) => {
        if (!image.complete || image.naturalWidth <= 0) errors.push(`image preview ${index} did not load`);
        if (!image.alt.trim()) errors.push(`image preview ${index} has empty alt text`);
        if (!image.source.startsWith('data:image/')) errors.push(`image preview ${index} is not embedded safely`);
      });
      const reviewRegion = page.locator('.dc-image-review[role="region"][aria-live="polite"]');
      if (await reviewRegion.count() !== 1) errors.push('image review is missing its accessible live region');
    }
    if (pageSpec.name === 'generation-qa-placeholder') {
      const classifications = spec.source_truth.artifacts.filter((item) => item.path).map((item) => item.review_classification);
      if (!classifications.length || classifications.some((value) => value !== 'illustrative_placeholder')) {
        errors.push('placeholder QA contains a non-placeholder image classification');
      }
      const actionKinds = spec.interactions.actions.map((action) => action.kind);
      if (!actionKinds.includes('request_revision') || actionKinds.some((kind) => !['request_revision', 'stop'].includes(kind))) {
        errors.push('placeholder QA exposes an unsafe action');
      }
      const mediaStatus = (await page.locator('.dc-qa-media-status').textContent() || '').trim();
      if (!mediaStatus.includes('暂不能确认使用')) errors.push('placeholder QA missing explicit unusable status');
    }
    const recommendation = spec.presentation.recommendation;
    if (recommendation) {
      const recommended = spec.presentation.options.find((option) => option.id === recommendation.option_id);
      const recommendationNode = page.locator('[data-dc-recommendation]');
      if (await recommendationNode.count() !== 1) errors.push('recommendation is not rendered as a distinct region');
      else {
        const renderedId = await recommendationNode.getAttribute('data-dc-recommended-option');
        const renderedName = (await page.locator('[data-dc-recommendation-name]').textContent() || '').trim();
        const renderedReason = (await page.locator('[data-dc-recommendation-reason]').textContent() || '').trim();
        if (renderedId !== recommendation.option_id) errors.push(`recommended option id mismatch: ${renderedId} != ${recommendation.option_id}`);
        if (recommended && renderedName !== recommended.label) errors.push(`recommended option label mismatch: ${renderedName} != ${recommended.label}`);
        if (renderedReason !== recommendation.reason) errors.push('recommendation reason mismatch');
      }
    }
    for (let index = 0; index < spec.presentation.options.length; index += 1) {
      const expectedOption = spec.presentation.options[index];
      const choice = page.locator('[data-dc-choice]').nth(index);
      await choice.focus();
      await page.keyboard.press('Enter');
      const actual = await page.evaluate(() => ({
        name: (document.querySelector('[data-dc-detail-name]')?.textContent || '').trim(),
        summary: (document.querySelector('[data-dc-detail-summary]')?.textContent || '').trim(),
        tradeoff: (document.querySelector('[data-dc-detail-tradeoff]')?.textContent || '').trim(),
        status: (document.querySelector('[data-dc-status]')?.textContent || '').trim(),
        pressed: Array.from(document.querySelectorAll('[data-dc-choice]')).map((node) => node.getAttribute('aria-pressed')),
        visiblePreviews: Array.from(document.querySelectorAll('[data-dc-image-preview]')).filter((node) => {
          const style = window.getComputedStyle(node);
          const rect = node.getBoundingClientRect();
          return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
        }).map((node) => node.dataset.dcImagePreview),
        details: Object.fromEntries(Array.from(document.querySelectorAll('[data-dc-detail-row]:not([hidden])')).map((row) => {
          const id = row.dataset.dcDetailRow;
          return [id, (row.querySelector('[data-dc-detail-value]')?.textContent || '').trim()];
        })),
      }));
      if (actual.name !== expectedOption.label) errors.push(`option ${expectedOption.id} name mismatch: ${actual.name} != ${expectedOption.label}`);
      if (actual.summary !== expectedOption.summary) errors.push(`option ${expectedOption.id} summary mismatch`);
      if (actual.tradeoff !== expectedOption.tradeoff) errors.push(`option ${expectedOption.id} director judgment mismatch`);
      if (previews.some((preview) => preview.option_id === expectedOption.id)
          && (actual.visiblePreviews.length !== 1 || actual.visiblePreviews[0] !== expectedOption.id)) {
        errors.push(`option ${expectedOption.id} image preview did not switch with selection`);
      }
      if (!actual.status.includes(`已选择“${expectedOption.label}”`) || !actual.status.includes('发送后才会确认')) {
        errors.push(`option ${expectedOption.id} preview status mismatch`);
      }
      actual.pressed.forEach((value, pressedIndex) => {
        const expectedPressed = pressedIndex === index ? 'true' : 'false';
        if (value !== expectedPressed) errors.push(`option ${expectedOption.id} aria-pressed state mismatch at ${pressedIndex}`);
      });
      const expectedDetails = Object.fromEntries((expectedOption.details || []).map((detail) => [detail.id, detail.value]));
      if (JSON.stringify(actual.details) !== JSON.stringify(expectedDetails)) {
        errors.push(`option ${expectedOption.id} detail set mismatch`);
      }
    }
  }

  const curveControlCount = await page.locator('[data-dc-curve-series]').count();
  if (curveControlCount) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const curve = spec.presentation.fields.find((field) => field.id === 'story_curve')?.value;
    if (!curve || curveControlCount !== curve.series.length) {
      errors.push(`curve control count ${curveControlCount} does not match series data`);
    } else {
      const paths = page.locator('[data-dc-curve-path]');
      if (await paths.count() !== curve.series.length) errors.push('curve path count does not match series data');
      const annotationCount = await page.locator('.dc-curve-annotations > span').count();
      if (annotationCount !== (curve.annotations || []).slice(0, 5).length) errors.push('curve annotation count mismatch');
      for (let index = 0; index < curve.series.length; index += 1) {
        const expectedSeries = curve.series[index];
        await page.locator('[data-dc-curve-series]').nth(index).click();
        const state = await page.evaluate(() => ({
          insight: (document.querySelector('[data-dc-curve-insight]')?.textContent || '').trim(),
          pressed: Array.from(document.querySelectorAll('[data-dc-curve-series]')).map((node) => node.getAttribute('aria-pressed')),
          focusedPaths: document.querySelectorAll('.dc-curve-path.is-focused').length,
          dimmedPaths: document.querySelectorAll('.dc-curve-path.is-dimmed').length,
        }));
        if (state.insight !== expectedSeries.insight) errors.push(`curve ${expectedSeries.id} insight mismatch`);
        state.pressed.forEach((value, pressedIndex) => {
          const expectedPressed = pressedIndex === index ? 'true' : 'false';
          if (value !== expectedPressed) errors.push(`curve ${expectedSeries.id} aria-pressed mismatch at ${pressedIndex}`);
        });
        if (state.focusedPaths !== 1 || state.dimmedPaths !== curve.series.length - 1) {
          errors.push(`curve ${expectedSeries.id} focus styling mismatch`);
        }
      }
    }
  }

  const shotControlCount = await page.locator('[data-dc-shot]').count();
  if (shotControlCount) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const rhythm = spec.presentation.fields.find((field) => field.id === 'shot_rhythm')?.value;
    if (!rhythm || shotControlCount !== rhythm.shots.length) {
      errors.push(`shot control count ${shotControlCount} does not match shot data`);
    } else {
      const laneCount = 6;
      const bandCount = await page.locator('[data-dc-shot-band]').count();
      if (bandCount !== rhythm.shots.length * laneCount) errors.push('shot band count does not match lanes and shots');
      if (await page.locator('[data-dc-shot-mobile]').count() !== rhythm.shots.length) errors.push('mobile shot row count mismatch');
      for (let index = 0; index < rhythm.shots.length; index += 1) {
        const expectedShot = rhythm.shots[index];
        await page.locator('[data-dc-shot]').nth(index).click();
        const state = await page.evaluate(() => ({
          detail: (document.querySelector('[data-dc-shot-detail]')?.textContent || '').trim(),
          pressed: Array.from(document.querySelectorAll('[data-dc-shot]')).map((node) => node.getAttribute('aria-pressed')),
          selectedBands: document.querySelectorAll('.dc-shot-band.is-selected').length,
          selectedMobileRows: document.querySelectorAll('.dc-shot-mobile-row.is-selected').length,
        }));
        for (const expectedText of [expectedShot.id.toUpperCase(), expectedShot.label, expectedShot.size, expectedShot.movement, expectedShot.risk]) {
          if (!state.detail.includes(expectedText)) errors.push(`shot ${expectedShot.id} detail missing ${expectedText}`);
        }
        state.pressed.forEach((value, pressedIndex) => {
          const expectedPressed = pressedIndex === index ? 'true' : 'false';
          if (value !== expectedPressed) errors.push(`shot ${expectedShot.id} aria-pressed mismatch at ${pressedIndex}`);
        });
        if (state.selectedBands !== laneCount || state.selectedMobileRows !== 1) {
          errors.push(`shot ${expectedShot.id} selected-state projection mismatch`);
        }
      }
    }
  }

  const graphNodeCount = await page.locator('[data-dc-graph-node]').count();
  if (graphNodeCount) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const graph = spec.presentation.fields.find((field) => field.id === 'asset_graph')?.value;
    if (!graph || graphNodeCount !== graph.nodes.length) {
      errors.push(`graph node count ${graphNodeCount} does not match graph data`);
    } else {
      const edgeCount = await page.locator('[data-dc-graph-edge]').count();
      if (edgeCount !== graph.edges.length) errors.push(`graph edge count ${edgeCount} does not match graph data`);
      const zeroLengthEdges = await page.locator('[data-dc-graph-edge]').evaluateAll((paths) => paths.filter((path) => path.getTotalLength() <= 1).length);
      if (zeroLengthEdges) errors.push(`${zeroLengthEdges} graph edges have zero geometry`);
      for (let index = 0; index < graph.nodes.length; index += 1) {
        const expectedNode = graph.nodes[index];
        await page.locator('[data-dc-graph-node]').nth(index).click();
        const incidentCount = graph.edges.filter((edge) => edge.source === expectedNode.id || edge.target === expectedNode.id).length;
        const state = await page.evaluate(() => ({
          detail: (document.querySelector('[data-dc-graph-detail]')?.textContent || '').trim(),
          pressed: Array.from(document.querySelectorAll('[data-dc-graph-node]')).map((node) => node.getAttribute('aria-pressed')),
          highlightedEdges: document.querySelectorAll('.dc-graph-edge.is-highlighted').length,
          dimmedEdges: document.querySelectorAll('.dc-graph-edge.is-dimmed').length,
        }));
        if (!state.detail.includes(expectedNode.label) || !state.detail.includes(expectedNode.detail)) {
          errors.push(`graph node ${expectedNode.id} detail mismatch`);
        }
        state.pressed.forEach((value, pressedIndex) => {
          const expectedPressed = pressedIndex === index ? 'true' : 'false';
          if (value !== expectedPressed) errors.push(`graph node ${expectedNode.id} aria-pressed mismatch at ${pressedIndex}`);
        });
        if (state.highlightedEdges !== incidentCount || state.dimmedEdges !== graph.edges.length - incidentCount) {
          errors.push(`graph node ${expectedNode.id} edge projection mismatch`);
        }
      }
    }
  }

  const qaCandidateCount = await page.locator('[data-dc-qa-candidate]').count();
  if (qaCandidateCount) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const qa = spec.presentation.fields.find((field) => field.id === 'qa_delta')?.value;
    if (!qa || qaCandidateCount !== qa.candidates.length) {
      errors.push(`QA candidate count ${qaCandidateCount} does not match QA data`);
    } else {
      const resultCount = await page.locator('.dc-qa-result').count();
      if (resultCount !== qa.dimensions.length * qa.candidates.length) errors.push('QA result cell count mismatch');
      for (let index = 0; index < qa.candidates.length; index += 1) {
        const candidate = qa.candidates[index];
        await page.locator('[data-dc-qa-candidate]').nth(index).click();
        const expectedSelectedCells = qa.dimensions.length + 1;
        const state = await page.evaluate(() => ({
          judgment: (document.querySelector('[data-dc-qa-judgment]')?.textContent || '').trim(),
          blocker: (document.querySelector('[data-dc-qa-blocker]')?.textContent || '').trim(),
          retry: (document.querySelector('[data-dc-qa-retry]')?.textContent || '').trim(),
          preserve: (document.querySelector('[data-dc-qa-preserve]')?.textContent || '').trim(),
          actionLabel: (document.querySelector('.btn-primary[data-dc-action]')?.textContent || '').trim(),
          selectedCells: document.querySelectorAll('[data-dc-qa-column].is-selected').length,
        }));
        if (state.judgment !== candidate.judgment) errors.push(`QA ${candidate.id} judgment mismatch`);
        if (state.blocker !== candidate.blocker) errors.push(`QA ${candidate.id} blocker mismatch`);
        if (state.retry !== candidate.retry) errors.push(`QA ${candidate.id} retry mismatch`);
        if (state.preserve !== candidate.preserve) errors.push(`QA ${candidate.id} preserve mismatch`);
        if (state.actionLabel !== candidate.action_label) errors.push(`QA ${candidate.id} action label mismatch`);
        if (state.selectedCells !== expectedSelectedCells) errors.push(`QA ${candidate.id} selected column mismatch`);
      }
    }
  }

  const boardDirectionCount = await page.locator('[data-dc-board-direction]').count();
  if (boardDirectionCount) {
    const spec = await page.evaluate(() => {
      const dataNode = document.querySelector('script[type="application/json"]');
      return JSON.parse(dataNode.textContent);
    });
    const board = spec.presentation.fields.find((field) => field.id === 'visual_board')?.value;
    if (!board || boardDirectionCount !== board.directions.length) {
      errors.push(`visual board direction count ${boardDirectionCount} does not match board data`);
    } else {
      for (let index = 0; index < board.directions.length; index += 1) {
        const direction = board.directions[index];
        await page.locator('[data-dc-board-direction]').nth(index).click();
        const state = await page.evaluate(() => ({
          palette: Array.from(document.querySelectorAll('[data-dc-board-palette] .dc-swatch-item')).map((item) => ({
            label: (item.querySelector('.text-small')?.textContent || '').trim(),
            color: item.querySelector('.dc-swatch')?.style.getPropertyValue('--dc-swatch').trim() || '',
          })),
          lighting: (document.querySelector('[data-dc-board-lighting]')?.textContent || '').trim(),
          materials: Array.from(document.querySelectorAll('[data-dc-board-materials] .viz-badge')).map((node) => node.textContent.trim()),
          optics: Array.from(document.querySelectorAll('[data-dc-board-optics] .viz-badge')).map((node) => node.textContent.trim()),
          allow: Array.from(document.querySelectorAll('[data-dc-board-allow] .viz-badge')).map((node) => node.textContent.trim()),
          avoid: Array.from(document.querySelectorAll('[data-dc-board-avoid] .viz-badge')).map((node) => node.textContent.trim()),
          judgment: (document.querySelector('[data-dc-board-judgment]')?.textContent || '').trim(),
          impact: (document.querySelector('[data-dc-board-impact]')?.textContent || '').trim(),
        }));
        if (JSON.stringify(state.palette) !== JSON.stringify(direction.palette)) errors.push(`visual board ${direction.id} palette mismatch`);
        if (state.lighting !== direction.lighting) errors.push(`visual board ${direction.id} lighting mismatch`);
        for (const key of ['materials', 'optics', 'allow', 'avoid']) {
          if (JSON.stringify(state[key]) !== JSON.stringify(direction[key])) errors.push(`visual board ${direction.id} ${key} mismatch`);
        }
        if (state.judgment !== direction.judgment) errors.push(`visual board ${direction.id} judgment mismatch`);
        if (state.impact !== direction.impact) errors.push(`visual board ${direction.id} impact mismatch`);
      }
    }
  }

  if (viewport === 736 && theme === 'light' && mode === 'default' && pageSpec.surface_kind !== 'confirmation') {
    const primary = page.locator('.btn-primary[data-dc-action]');
    await primary.focus();
    await page.keyboard.press('Enter');
    const followUps = await page.evaluate(() => window.__dcFollowUps);
    if (followUps.length !== 1) errors.push(`expected one follow-up, got ${followUps.length}`);
    else {
      const prompt = followUps[0].prompt || '';
      if (!prompt.includes('当前项目记录') || !prompt.includes('当前阶段')) {
        errors.push('follow-up prompt missing project-record or stage binding');
      }
      if (/\bgate\b|artifact|sha256|source truth|writeback|receipt|\bcandidate-[a-z0-9_-]+\b/i.test(prompt)) {
        errors.push('follow-up prompt leaks backstage implementation terms');
      }
      if (choiceCount > 1) {
        const lastChoice = page.locator('[data-dc-choice]').last();
        const lastLabel = (await lastChoice.textContent() || '').trim();
        if (!prompt.includes(lastLabel)) {
          errors.push('follow-up prompt does not match the currently selected option');
        }
      }
      if (qaCandidateCount) {
        const qaState = await page.evaluate(() => {
          const dataNode = document.querySelector('script[type="application/json"]');
          const spec = JSON.parse(dataNode.textContent);
          const actionId = document.querySelector('.btn-primary[data-dc-action]')?.dataset.dcAction;
          return {
            qa: spec.presentation.fields.find((field) => field.id === 'qa_delta')?.value,
            action: spec.interactions.actions.find((item) => item.id === actionId),
          };
        });
        const lastCandidate = qaState.qa?.candidates?.[qaState.qa.candidates.length - 1];
        if (lastCandidate && qaState.action?.kind === 'retry_smallest' && !prompt.includes(lastCandidate.conversation_intent)) {
          errors.push('follow-up prompt does not use the selected QA candidate intent');
        }
        if (lastCandidate && followUps[0].title !== lastCandidate.action_label) {
          errors.push('follow-up title does not match the selected QA candidate action');
        }
      }
    }
  }

  const visibleText = await page.locator('body').innerText();
  if (/\bgate\b|artifact|sha256|source truth|writeback|receipt|prompt-only|项目写回|新建锁|保留锁/i.test(visibleText)) {
    errors.push('visible surface leaks backstage implementation terms');
  }

  await page.waitForTimeout(150);

  const layout = await page.evaluate(() => {
    const rootNode = document.querySelector('[data-dircreative-visual]');
    const selectors = '[data-dircreative-visual], [data-dc-action], [data-dc-choice], .card, .dc-header, .dc-stage-rail, .dc-timeline-row';
    const badBounds = Array.from(document.querySelectorAll(selectors)).flatMap((node) => {
      const rect = node.getBoundingClientRect();
      if (rect.left < -1 || rect.right > document.documentElement.clientWidth + 1) {
        return [`${node.tagName}.${node.className}: ${rect.left}..${rect.right}`];
      }
      return [];
    });
    const nestedScroll = Array.from(rootNode.querySelectorAll('*')).flatMap((node) => {
      const style = getComputedStyle(node);
      if (['auto', 'scroll'].includes(style.overflowX) || ['auto', 'scroll'].includes(style.overflowY)) {
        return [`${node.tagName}.${node.className}`];
      }
      return [];
    });
    const targetSelector = [
      '[data-dc-action]', '[data-dc-choice]', '[data-dc-curve-series]', '[data-dc-shot]',
      '[data-dc-graph-node]', '[data-dc-qa-candidate]', '[data-dc-board-direction]',
    ].join(', ');
    const smallTargets = Array.from(rootNode.querySelectorAll(targetSelector)).flatMap((node) => {
      const rect = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') return [];
      if (rect.width < 24 || rect.height < 24) return [`${(node.textContent || '').trim()}: ${rect.width.toFixed(1)}x${rect.height.toFixed(1)}`];
      return [];
    });
    const readableSelector = [
      '.btn', '.dc-detail-row > span', '.dc-header > *', '.dc-status', '.dc-board-section',
      '.dc-qa-result', '.dc-shot-mobile-row', '.dc-graph-detail', '.dc-curve-insight',
    ].join(', ');
    const clippedContent = Array.from(rootNode.querySelectorAll(readableSelector)).flatMap((node) => {
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') return [];
      const overflowWidth = node.scrollWidth - node.clientWidth;
      const overflowHeight = node.scrollHeight - node.clientHeight;
      if (overflowWidth > 1 || overflowHeight > 1) {
        return [`${node.tagName}.${node.className}: +${overflowWidth}px/+${overflowHeight}px`];
      }
      return [];
    });
    const undersizedSecondaryText = Array.from(rootNode.querySelectorAll('.text-small')).flatMap((node) => {
      const style = getComputedStyle(node);
      if (style.display === 'none' || style.visibility === 'hidden') return [];
      const size = Number.parseFloat(style.fontSize);
      return size < 11 ? [`${(node.textContent || '').trim()}: ${size}px`] : [];
    });
    const curveText = Array.from(rootNode.querySelectorAll('.dc-story-curve text')).map((node) => ({
      label: (node.textContent || '').trim(),
      rect: node.getBoundingClientRect(),
    }));
    const curveTextOverlaps = [];
    for (let first = 0; first < curveText.length; first += 1) {
      for (let second = first + 1; second < curveText.length; second += 1) {
        const a = curveText[first];
        const b = curveText[second];
        const overlapX = Math.min(a.rect.right, b.rect.right) - Math.max(a.rect.left, b.rect.left);
        const overlapY = Math.min(a.rect.bottom, b.rect.bottom) - Math.max(a.rect.top, b.rect.top);
        if (overlapX > 1 && overlapY > 1) curveTextOverlaps.push(`${a.label}/${b.label}`);
      }
    }
    return {
      horizontalOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      badBounds,
      nestedScroll,
      curveTextOverlaps,
      smallTargets,
      clippedContent,
      undersizedSecondaryText,
    };
  });
  if (layout.horizontalOverflow > 1) errors.push(`horizontal overflow ${layout.horizontalOverflow}px`);
  if (layout.badBounds.length) errors.push(`out-of-bounds elements: ${layout.badBounds.join('; ')}`);
  if (layout.nestedScroll.length) errors.push(`nested scroll surfaces: ${layout.nestedScroll.join('; ')}`);
  if (layout.curveTextOverlaps.length) errors.push(`overlapping curve labels: ${layout.curveTextOverlaps.join('; ')}`);
  if (layout.smallTargets.length) errors.push(`undersized targets: ${layout.smallTargets.join('; ')}`);
  if (layout.clippedContent.length) errors.push(`clipped content: ${layout.clippedContent.join('; ')}`);
  if (layout.undersizedSecondaryText.length) errors.push(`secondary text below 11px: ${layout.undersizedSecondaryText.join('; ')}`);

  const screenshot = path.join(outputDir, `${pageSpec.name}-${viewport}-${theme}-${mode}.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  await page.close();
  return { name: pageSpec.name, viewport, theme, mode, screenshot, errors, layout };
}

async function main() {
  const outputDir = path.resolve(argument('--output-dir', '/tmp/dircreative-chat-visualizations'));
  const chrome = argument('--chrome', chromium.executablePath());
  const manifest = JSON.parse(fs.readFileSync(path.join(outputDir, 'manifest.json'), 'utf8'));
  if (!fs.existsSync(chrome)) throw new Error(`Playwright browser executable not found: ${chrome}. Run: npx playwright install chromium`);
  const browser = await chromium.launch({ headless: true, executablePath: chrome });
  const results = [];
  const scenarios = [
    { viewport: 736, theme: 'light', mode: 'default' },
    { viewport: 320, theme: 'light', mode: 'default' },
    { viewport: 736, theme: 'dark', mode: 'default' },
    { viewport: 320, theme: 'dark', mode: 'default' },
    { viewport: 320, theme: 'light', mode: 'text-spacing' },
    { viewport: 736, theme: 'light', mode: 'large-text' },
  ];
  try {
    for (const pageSpec of manifest.pages) {
      for (const scenario of scenarios) {
        results.push(await auditPage(browser, pageSpec, outputDir, scenario.viewport, scenario.theme, scenario.mode));
      }
    }
  } finally {
    await browser.close();
  }
  const failures = results.flatMap((result) => result.errors.map((error) => `${result.name}/${result.viewport}/${result.theme}/${result.mode}: ${error}`));
  const receipt = {
    status: failures.length ? 'fail' : 'pass',
    chrome,
    page_count: manifest.pages.length,
    checks: results,
    failures,
  };
  fs.writeFileSync(path.join(outputDir, 'browser-audit.json'), JSON.stringify(receipt, null, 2) + '\n');
  console.log('DIRcreative Chat Visualization Browser Audit');
  console.log(`pages: ${manifest.pages.length}`);
  console.log(`checks: ${results.length}`);
  console.log(`failures: ${failures.length}`);
  for (const failure of failures) console.log(`- ${failure}`);
  console.log(`CHAT_VISUALIZATION_BROWSER_AUDIT: ${failures.length ? 'FAIL' : 'PASS'}`);
  process.exitCode = failures.length ? 1 : 0;
}

main().catch((error) => {
  console.error(error.stack || error.message);
  process.exitCode = 1;
});
