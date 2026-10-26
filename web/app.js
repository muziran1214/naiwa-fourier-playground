(() => {
  'use strict';

  const data = window.NAIWA_SCENE;
  const $ = (id) => document.getElementById(id);
  const canvas = $('stage');
  const ctx = canvas.getContext('2d');
  const cover = $('loadingCover');
  if (!data || !ctx) {
    cover.querySelector('strong').textContent = '动画资源还没准备好';
    cover.lastElementChild.textContent = '请完整保留 web 文件夹，或使用导出的单文件 HTML。';
    return;
  }

  const placement = data.placement;
  const TAU = Math.PI * 2;
  const coefficients = data.coefficients;
  const phases = [
    { start: 0, label: '01 / 谐波唤醒', tip: '一点一点，把快乐画出来。' },
    { start: 6, label: '02 / 慢慢描绘', tip: '跟着笔尖，发现一只奶蛙。' },
    { start: 16.8, label: '03 / 奶蛙显影', tip: '准备好了吗？戳一下奶蛙。' },
    { start: 20.4, label: '04 / 捧腹大笑', tip: '快乐这种事，再来亿遍也可以。' },
  ];
  const state = {
    ready: false, playing: false, time: 0, speed: 1, limit: 750,
    muted: true, wheels: true, trace: true, follow: true, loop: true,
    anchorTime: 0, anchorNow: 0, audioActive: false, dirty: true,
  };
  const audio = $('soundtrack');
  audio.src = data.audio;
  audio.preload = 'auto';
  audio.muted = true;
  const curveCache = new Map([[750, data.reconstruction]]);
  let frog;
  let revealPages;
  let laughPages;
  let playAttempt = 0;
  let noticeTimer;
  let lastUiUpdate = 0;
  let camera = { zoom: 1, cx: 360, cy: 640 };

  function clamp(value, low, high) {
    return Math.max(low, Math.min(high, value));
  }

  function smoothstep(low, high, value) {
    const t = clamp((value - low) / (high - low), 0, 1);
    return t * t * (3 - 2 * t);
  }

  function notify(message) {
    $('notice').textContent = message;
    $('notice').classList.add('visible');
    clearTimeout(noticeTimer);
    noticeTimer = setTimeout(() => $('notice').classList.remove('visible'), 3400);
  }

  function loadImage(source) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error('Image failed to load.'));
      image.src = source;
    });
  }

  function phaseAt(time) {
    for (let i = phases.length - 1; i >= 0; i -= 1) {
      if (time >= phases[i].start) return i;
    }
    return 0;
  }

  function curveFor(count) {
    if (curveCache.has(count)) return curveCache.get(count);
    const points = [];
    for (let j = 0; j < 768; j += 1) {
      const u = j / 768;
      let x = placement.cx;
      let y = placement.cy;
      for (let i = 0; i < count; i += 1) {
        const [real, imaginary, frequency] = coefficients[i];
        const angle = TAU * frequency * u;
        x += real * Math.cos(angle) - imaginary * Math.sin(angle);
        y += real * Math.sin(angle) + imaginary * Math.cos(angle);
      }
      points.push([x, y]);
    }
    if (curveCache.size > 18) {
      const candidate = [...curveCache.keys()].find((key) => key !== 750);
      curveCache.delete(candidate);
    }
    curveCache.set(count, points);
    return points;
  }

  function sceneAt(time) {
    const phase = phaseAt(time);
    const steps = [4, 10, 24, 65, 180, 750];
    const count = phase === 0 ? Math.min(state.limit, steps[Math.min(5, Math.floor(time))]) : state.limit;
    const u = phase === 0 ? (time / 4) % 1 : phase === 1 ? clamp((time - 6) / 10.8, 0, 1) : phase === 2 ? ((time - 16.8) / 7.2) % 1 : ((time - 20.4) / 3.6) % 1;
    const chain = [[placement.cx, placement.cy]];
    let x = placement.cx;
    let y = placement.cy;
    for (let i = 0; i < count; i += 1) {
      const [real, imaginary, frequency] = coefficients[i];
      const angle = TAU * frequency * u;
      x += real * Math.cos(angle) - imaginary * Math.sin(angle);
      y += real * Math.sin(angle) + imaginary * Math.cos(angle);
      chain.push([x, y]);
    }
    return { time, phase, count, u, chain, tip: [x, y], curve: curveFor(count) };
  }

  const background = document.createElement('canvas');
  background.width = data.width;
  background.height = data.height;
  const bg = background.getContext('2d');
  const gradient = bg.createRadialGradient(350, 540, 50, 350, 600, 1000);
  gradient.addColorStop(0, '#fdfcf7');
  gradient.addColorStop(1, '#efecde');
  bg.fillStyle = gradient;
  bg.fillRect(0, 0, 720, 1280);
  bg.fillStyle = '#d7d5be';
  for (let y = 130; y < 1135; y += 36) {
    for (let x = 18; x < 720; x += 36) {
      bg.beginPath();
      bg.arc(x, y, 0.7, 0, TAU);
      bg.fill();
    }
  }

  function atlasFrame(target, atlas, pages, index, opacity = 1) {
    const frame = clamp(Math.floor(index), 0, atlas.count - 1);
    const perPage = atlas.cols * atlas.rows;
    const local = frame % perPage;
    target.save();
    target.globalAlpha *= opacity;
    target.drawImage(
      pages[Math.floor(frame / perPage)],
      (local % atlas.cols) * atlas.width, Math.floor(local / atlas.cols) * atlas.height,
      atlas.width, atlas.height, placement.x, placement.y, placement.width, placement.height,
    );
    target.restore();
  }

  function character(target, scene) {
    const { phase, time, u } = scene;
    if (time >= data.laugh.start) {
      atlasFrame(target, data.laugh, laughPages, (time - data.laugh.start) * data.laugh.fps);
    } else if (phase === 0) {
      target.save();
      target.globalAlpha = 0.075 + Math.min(time / 6, 1) * 0.1;
      target.drawImage(frog, placement.x, placement.y, placement.width, placement.height);
      target.restore();
    } else if (phase === 1) {
      const frame = u * (data.reveal.count - 1);
      const lower = Math.floor(frame);
      const mix = frame - lower;
      atlasFrame(target, data.reveal, revealPages, lower, 1 - mix);
      if (mix > 0) atlasFrame(target, data.reveal, revealPages, lower + 1, mix);
    } else {
      target.save();
      target.globalAlpha = 0.7 + smoothstep(16.8, 17.9, time) * 0.3;
      target.drawImage(frog, placement.x, placement.y, placement.width, placement.height);
      target.restore();
    }
  }

  function strokeCurve(target, points, end, skipBridges, color, width) {
    target.beginPath();
    let drawing = false;
    for (let i = 0; i < Math.min(end, points.length); i += 1) {
      if (skipBridges && data.bridge[Math.floor(i / points.length * data.bridge.length)]) {
        drawing = false;
        continue;
      }
      const [x, y] = points[i];
      if (drawing) target.lineTo(x, y);
      else target.moveTo(x, y);
      drawing = true;
    }
    target.strokeStyle = color;
    target.lineWidth = width;
    target.lineJoin = 'round';
    target.lineCap = 'round';
    target.stroke();
  }

  function trace(target, scene) {
    if (!state.trace || scene.phase === 3) return;
    const { phase, curve, u, time } = scene;
    const end = phase === 0 || phase === 2 ? curve.length : Math.max(2, Math.ceil(u * curve.length));
    target.save();
    target.globalAlpha = phase === 2 ? 1 - smoothstep(17.2, 19.6, time) : 1;
    if (phase === 0) strokeCurve(target, curve, end, false, '#e1bf6390', 6);
    strokeCurve(target, curve, end, phase !== 0, phase === 0 ? '#b5913b' : '#756537', 2.2);
    if (phase === 0) strokeCurve(target, curve, Math.ceil(u * curve.length), false, '#5b6235', 3.1);
    if (phase === 1) {
      const tail = curve.slice(Math.max(0, end - Math.round(curve.length * 0.028)), end);
      strokeCurve(target, tail, tail.length, false, '#e9b633', 3.2);
    }
    target.restore();
  }

  function wheels(target, scene) {
    if (!state.wheels) return;
    target.save();
    target.globalAlpha = scene.phase === 3 ? 0.1 : scene.phase === 2 ? 0.35 : 0.72;
    for (let i = 1; i < scene.chain.length; i += 1) {
      const [cx, cy] = scene.chain[i - 1];
      const [x, y] = scene.chain[i];
      const radius = Math.hypot(coefficients[i - 1][0], coefficients[i - 1][1]);
      const color = i < 8 ? '#c6a145' : i < 40 ? '#8b9b68' : '#a99c71';
      target.strokeStyle = color;
      if (i > 1 && radius > 1.7) {
        target.beginPath();
        target.arc(cx, cy, radius, 0, TAU);
        target.lineWidth = i < 8 ? 1.5 : 0.9;
        target.stroke();
      }
      target.beginPath();
      target.moveTo(cx, cy);
      target.lineTo(x, y);
      target.lineWidth = i < 9 ? 2.8 : 1.1;
      target.stroke();
      if (i < 14) {
        target.beginPath();
        target.arc(x, y, 3.8, 0, TAU);
        target.fillStyle = '#817744';
        target.fill();
      }
    }
    target.restore();
    if (scene.phase < 3) {
      target.save();
      target.shadowColor = '#e3b239';
      target.shadowBlur = 18;
      target.fillStyle = '#fff5c7';
      target.strokeStyle = '#d6a52e';
      target.lineWidth = 3;
      target.beginPath();
      target.arc(...scene.tip, 6.5, 0, TAU);
      target.fill();
      target.stroke();
      target.restore();
    }
  }

  function laughEffects(target, scene) {
    if (scene.time < 19.6) return;
    const { time } = scene;
    target.save();
    if (time < 20.4) {
      const p = (time - 19.6) / 0.8;
      target.strokeStyle = '#dbb343';
      target.globalAlpha = 1 - p * 0.7;
      target.lineWidth = 2;
      target.beginPath();
      target.arc(placement.x + 135 * 1.16, placement.y + 425 * 1.16, 15 + p * 110, 0, TAU);
      target.stroke();
    } else if (time < 27.6) {
      const mouth = data.mouth[Math.min(863, Math.floor(time * 30))];
      target.font = '600 31px "Microsoft YaHei", "PingFang SC", sans-serif';
      target.fillStyle = '#bd912d';
      target.fillText('哈哈哈哈!', 49, 222 + 8 * Math.sin(time * 20));
      if (time > 21.5) {
        target.fillStyle = '#7e935b';
        target.fillText('齁齁齁～', 482, 275 + 8 * Math.cos(time * 18));
      }
      if (mouth > 0.45) {
        const progress = ((time - 20.4) * 2.5) % 1;
        target.globalAlpha = (1 - progress) * 0.55;
        target.strokeStyle = '#d8ad48';
        target.lineWidth = 2;
        target.beginPath();
        target.arc(placement.x + 170, placement.y + 190, 25 + progress * 150, 0, TAU);
        target.stroke();
      }
    }
    target.restore();
  }

  function world(target, scene) {
    target.drawImage(background, 0, 0);
    character(target, scene);
    trace(target, scene);
    wheels(target, scene);
    laughEffects(target, scene);
  }

  function cameraFor(scene) {
    if (!state.follow) return { zoom: 1, cx: 360, cy: 640 };
    const amount = smoothstep(5.7, 6.6, scene.time) * (1 - smoothstep(16, 17.2, scene.time));
    const zoom = 1 + 0.95 * amount;
    const x = clamp(scene.tip[0], 360 / zoom + 10, 720 - 360 / zoom - 10);
    const y = clamp(scene.tip[1], 640 / zoom + 110, 1120 - 640 / zoom);
    return { zoom, cx: 360 + (x - 360) * amount, cy: 640 + (y - 640) * amount };
  }

  function spectrum(scene) {
    const values = data.spectrum[Math.min(863, Math.floor(scene.time * 30))];
    ctx.save();
    ctx.fillStyle = '#eeeddf';
    ctx.fillRect(93, 1164, 534, 1);
    for (let i = 0; i < values.length; i += 1) {
      const height = 3 + values[i] * 40;
      ctx.fillStyle = i < 16 ? '#8f9b6e' : '#cbb066';
      ctx.fillRect(99 + i * 16.5, 1150 - height, 7, height);
    }
    ctx.font = '11px "Segoe UI", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillStyle = '#9a9d83';
    ctx.fillText('SOUND & HARMONICS', 360, 1190);
    ctx.restore();
  }

  function draw() {
    if (!state.ready) return;
    const scene = sceneAt(state.time);
    camera = cameraFor(scene);
    ctx.clearRect(0, 0, data.width, data.height);
    ctx.save();
    ctx.translate(360, 640);
    ctx.scale(camera.zoom, camera.zoom);
    ctx.translate(-camera.cx, -camera.cy);
    world(ctx, scene);
    ctx.restore();
    if (scene.phase === 1 && camera.zoom > 1.2) {
      ctx.save();
      ctx.translate(518, 150);
      ctx.scale(0.235, 0.235);
      world(ctx, scene);
      ctx.lineWidth = 9;
      ctx.strokeStyle = '#c5b77a';
      ctx.strokeRect(0, 0, 720, 1280);
      ctx.lineWidth = 5;
      ctx.strokeStyle = '#d4ac43';
      ctx.strokeRect(camera.cx - 360 / camera.zoom, camera.cy - 640 / camera.zoom, 720 / camera.zoom, 1280 / camera.zoom);
      ctx.restore();
      ctx.fillStyle = '#7e805f';
      ctx.font = '11px "Segoe UI", sans-serif';
      ctx.fillText('OVERVIEW', 531, 172);
    }
    spectrum(scene);
    canvas.dataset.phase = String(scene.phase + 1);
    canvas.dataset.time = state.time.toFixed(3);
    canvas.dataset.harmonics = String(scene.count);
    state.dirty = false;
  }

  function updateUi() {
    const phase = phaseAt(state.time);
    $('currentTime').textContent = state.time.toFixed(1).padStart(4, '0');
    $('timeline').value = String(state.time);
    $('timeline').style.setProperty('--progress', `${state.time / data.duration * 100}%`);
    $('timeline').setAttribute('aria-valuetext', `${state.time.toFixed(1)} 秒，共 28.8 秒`);
    $('playIcon').textContent = state.playing ? 'Ⅱ' : '▶';
    $('playText').textContent = state.playing ? '暂停' : '播放';
    $('playPause').setAttribute('aria-label', state.playing ? '暂停动画' : '播放动画');
    $('phaseLabel').textContent = phases[phase].label;
    $('stageTip').textContent = phases[phase].tip;
    $('soundText').textContent = state.muted ? '声音关闭' : '声音开启';
    $('sound').setAttribute('aria-pressed', String(!state.muted));
    $('sound').title = state.muted ? '打开声音' : '关闭声音';
    document.querySelectorAll('[data-seek]').forEach((button, index) => {
      button.classList.toggle('active', phase === index);
      if (phase === index) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
    });
  }

  function syncClock() {
    if (!state.playing) return;
    state.time = clamp(state.audioActive ? audio.currentTime : state.anchorTime + (performance.now() - state.anchorNow) / 1000 * state.speed, 0, data.duration);
  }

  function resetClock() {
    state.anchorTime = state.time;
    state.anchorNow = performance.now();
  }

  async function startAudio() {
    const attempt = ++playAttempt;
    try {
      audio.currentTime = state.time;
      audio.playbackRate = state.speed;
      audio.muted = state.muted;
      await audio.play();
      if (attempt === playAttempt && state.playing) state.audioActive = true;
    } catch (error) {
      if (attempt !== playAttempt) return;
      state.audioActive = false;
      resetClock();
      if (!state.muted) notify('暂时无法播放声音，动画继续播放。再次点击声音按钮可重试。');
    }
  }

  function play() {
    if (!state.ready || state.playing) return;
    if (state.time >= data.duration - 0.01) state.time = 0;
    state.playing = true;
    resetClock();
    startAudio();
    updateUi();
  }

  function pause() {
    syncClock();
    state.playing = false;
    state.audioActive = false;
    playAttempt += 1;
    audio.pause();
    state.dirty = true;
    updateUi();
  }

  function seek(time) {
    if (!state.ready) return;
    const destination = clamp(time, 0, data.duration);
    if (destination >= data.duration) pause();
    state.time = destination;
    resetClock();
    try { audio.currentTime = Math.min(state.time, data.duration - 0.01); } catch (error) { /* Metadata can still be loading. */ }
    state.dirty = true;
    updateUi();
  }

  function finish() {
    state.time = data.duration;
    if (state.loop) {
      audio.pause();
      state.playing = false;
      state.audioActive = false;
      state.time = 0;
      play();
    } else {
      pause();
      state.time = data.duration;
      updateUi();
    }
    state.dirty = true;
  }

  function triggerLaugh() {
    if (!state.ready) return;
    state.muted = false;
    audio.muted = false;
    seek(20.4);
    if (state.playing && !state.audioActive) startAudio();
    play();
    notify('奶蛙：哈哈哈哈哈哈！');
  }

  function toggleSound() {
    if (!state.ready) return;
    state.muted = !state.muted;
    audio.muted = state.muted;
    if (state.playing && !state.audioActive) startAudio();
    updateUi();
  }

  function setHarmonics(value) {
    state.limit = clamp(Math.round(value), 4, 750);
    $('harmonics').value = String(state.limit);
    $('harmonicsValue').value = String(state.limit);
    $('harmonics').style.setProperty('--progress', `${(state.limit - 4) / 746 * 100}%`);
    document.querySelectorAll('[data-harmonics]').forEach((button) => {
      const active = Number(button.dataset.harmonics) === state.limit;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    state.dirty = true;
  }

  $('playPause').addEventListener('click', () => state.playing ? pause() : play());
  $('restart').addEventListener('click', () => { seek(0); play(); });
  $('sound').addEventListener('click', toggleSound);
  $('laugh').addEventListener('click', triggerLaugh);
  $('timeline').addEventListener('input', (event) => seek(Number(event.target.value)));
  $('harmonics').addEventListener('input', (event) => setHarmonics(Number(event.target.value)));
  document.querySelectorAll('[data-harmonics]').forEach((button) => button.addEventListener('click', () => setHarmonics(Number(button.dataset.harmonics))));
  document.querySelectorAll('[data-seek]').forEach((button) => button.addEventListener('click', () => seek(Number(button.dataset.seek))));
  document.querySelectorAll('[data-speed]').forEach((button) => button.addEventListener('click', () => {
    syncClock();
    state.speed = Number(button.dataset.speed);
    resetClock();
    audio.playbackRate = state.speed;
    $('speedValue').value = `${state.speed}×`;
    document.querySelectorAll('[data-speed]').forEach((item) => {
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-pressed', String(active));
    });
  }));
  for (const [id, property] of [['showWheels', 'wheels'], ['showTrace', 'trace'], ['followCamera', 'follow'], ['loop', 'loop']]) {
    $(id).addEventListener('change', (event) => {
      state[property] = event.target.checked;
      state.dirty = true;
    });
  }
  canvas.addEventListener('click', (event) => {
    const bounds = canvas.getBoundingClientRect();
    const displayScale = Math.min(bounds.width / 720, bounds.height / 1280);
    const x = (event.clientX - bounds.left - (bounds.width - 720 * displayScale) / 2) / displayScale;
    const y = (event.clientY - bounds.top - (bounds.height - 1280 * displayScale) / 2) / displayScale;
    const worldX = camera.cx + (x - 360) / camera.zoom;
    const worldY = camera.cy + (y - 640) / camera.zoom;
    if (worldX > placement.x && worldX < placement.x + placement.width && worldY > placement.y + 50 && worldY < placement.y + placement.height) triggerLaugh();
  });
  canvas.addEventListener('keydown', (event) => {
    if (event.code === 'Space' || event.key === 'Enter') {
      event.preventDefault();
      triggerLaugh();
    }
  });
  $('fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if ($('stageShell').requestFullscreen) await $('stageShell').requestFullscreen();
      else notify('当前浏览器不支持全屏，可使用横屏或浏览器缩放。');
    } catch (error) {
      notify('当前浏览器未允许全屏。');
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.altKey || event.ctrlKey || event.metaKey || event.target.closest('input, button, a, canvas, textarea, select')) return;
    if (event.code === 'Space') { event.preventDefault(); state.playing ? pause() : play(); }
    if (event.key.toLowerCase() === 'l') triggerLaugh();
    if (event.key.toLowerCase() === 'm') toggleSound();
    if (event.key === 'ArrowLeft') { event.preventDefault(); seek(state.time - 2); }
    if (event.key === 'ArrowRight') { event.preventDefault(); seek(state.time + 2); }
  });
  audio.addEventListener('ended', () => { if (state.playing) finish(); });

  function tick(now) {
    if (state.playing) {
      syncClock();
      if (state.time >= data.duration - 0.004) finish();
      state.dirty = true;
    }
    if (state.dirty) draw();
    if (state.playing && now - lastUiUpdate > 75) {
      updateUi();
      lastUiUpdate = now;
    }
    requestAnimationFrame(tick);
  }

  Promise.all([
    loadImage(data.image),
    Promise.all(data.reveal.pages.map(loadImage)),
    Promise.all(data.laugh.pages.map(loadImage)),
  ]).then((loaded) => {
    [frog, revealPages, laughPages] = loaded;
    state.ready = true;
    cover.hidden = true;
    document.body.dataset.ready = 'true';
    ['playPause', 'restart', 'sound', 'laugh', 'timeline'].forEach((id) => { $(id).disabled = false; });
    setHarmonics(750);
    updateUi();
    draw();
    requestAnimationFrame(tick);
  }).catch(() => {
    cover.querySelector('strong').textContent = '有些动画素材没有找到';
    cover.lastElementChild.textContent = '请完整保留 web/assets 文件夹，或打开导出的单文件 HTML。';
    notify('资源加载失败，请查看项目的 HTML 演示使用说明。');
  });
})();
