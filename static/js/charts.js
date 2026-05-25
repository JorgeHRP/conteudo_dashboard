// ── Conteúdo Insights — charts.js ──────────────────
// Utilitários compartilhados de gráficos e formatação.
// Incluir após Chart.js em cada template de dashboard.

const _CH = {};

// ── Formatação ──────────────────────────────────────
const fmt  = n => Number(n).toLocaleString('pt-BR');
const fmtK = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(0)+'K' : String(n);
const pct  = (a,b) => b > 0 ? (a/b*100).toFixed(1)+'%' : '—';
const rCls = i => ['g','s','b'][i] || '';

// ── Helpers DOM de filtros (compartilhados por todos os templates) ────
const v    = id => { const e = document.getElementById(id); return e ? e.value : ''; };
const setV = (id, val) => { const e = document.getElementById(id); if (e) e.value = val; };

// ── Typeahead de Curso (reutilizável por todas as páginas) ────────────
function setupCursoTypeahead(lista) {
  const input = document.getElementById('f-curso-input');
  const dd    = document.getElementById('curso-dd');
  if (!input || !dd) return;
  let _open = false;
  function _pos() { const r=input.getBoundingClientRect(); dd.style.top=(r.bottom+4)+'px'; dd.style.maxWidth=(window.innerWidth-16)+'px'; dd.style.left=Math.min(r.left,window.innerWidth-dd.offsetWidth-8)+'px'; }
  function _close() { dd.style.display='none'; _open=false; window.removeEventListener('scroll',_pos,true); }
  input.addEventListener('focus', () => { if (!_open) input.dispatchEvent(new Event('input')); });
  input.addEventListener('input', () => {
    const q = input.value.trim().toLowerCase();
    const hits = q.length < 2
      ? lista
      : lista.filter(x => x.toLowerCase().includes(q)).slice(0, 40);
    if (!hits.length) { _close(); return; }
    dd.innerHTML = hits.map(x => `
      <div class="curso-opt"
           style="padding:7px 12px;cursor:pointer;font-family:var(--mono);font-size:.68rem;
                  color:var(--tx1);border-bottom:1px solid var(--line);white-space:nowrap;
                  overflow:hidden;text-overflow:ellipsis">
        ${x}
      </div>`).join('');
    dd.querySelectorAll('.curso-opt').forEach(el => {
      el.addEventListener('mouseenter', () => el.style.background = 'var(--bg-card2)');
      el.addEventListener('mouseleave', () => el.style.background = '');
      el.addEventListener('click', () => { input.value = el.textContent.trim(); _close(); });
    });
    dd.style.display = 'block';
    if (!_open) { _open=true; window.addEventListener('scroll',_pos,{passive:true,capture:true}); }
    _pos();
  });
  document.addEventListener('click', e => {
    if (_open && !dd.contains(e.target) && e.target !== input) { _close(); }
  });
  input.addEventListener('keydown', e => { if (e.key === 'Escape') { _close(); } });
}

// ── Theme ───────────────────────────────────────────
function getThemeColors() {
  const dark = document.documentElement.dataset.theme !== 'light';
  return dark
    ? { grid:'rgba(255,255,255,0.05)', tick:'#4a6070', ttbg:'#171c26', ttbrd:'rgba(255,255,255,0.08)', tttxt:'#f0f4f8', ttmut:'#4a6070', border:'#171c26' }
    : { grid:'rgba(0,0,0,0.07)',       tick:'#8fa3b8', ttbg:'#ffffff',  ttbrd:'rgba(0,0,0,0.1)',       tttxt:'#0d1117',  ttmut:'#8fa3b8',  border:'#ffffff' };
}

function baseOpts() {
  const c = getThemeColors();
  return {
    responsive: true,
    animation: { duration:500, easing:'easeOutQuart' },
    plugins: {
      legend: { display:false },
      tooltip: {
        backgroundColor: c.ttbg, borderColor: c.ttbrd, borderWidth:1,
        titleColor: c.tttxt, bodyColor: c.ttmut,
        titleFont: { family:"'Inter'", weight:'700', size:12 },
        bodyFont:  { family:"'DM Mono'", size:11 },
        padding:10, cornerRadius:2,
        callbacks: { label: x => '  '+Number(x.raw).toLocaleString('pt-BR') }
      }
    },
    scales: {
      x: { ticks:{color:c.tick, maxTicksLimit:8}, grid:{color:c.grid}, border:{color:c.grid} },
      y: { ticks:{color:c.tick, maxTicksLimit:6}, grid:{color:c.grid}, border:{color:c.grid} }
    }
  };
}

Chart.defaults.font.family = "'DM Mono', monospace";
Chart.defaults.font.size   = 11;

// ── Helpers DOM ─────────────────────────────────────
function showC(loadId, canvasId) {
  const l=document.getElementById(loadId), c=document.getElementById(canvasId);
  if(l) l.style.display='none';
  if(c) c.style.display='block';
}
function showT(loadId, tableId) {
  const l=document.getElementById(loadId), t=document.getElementById(tableId);
  if(l) l.style.display='none';
  if(t) t.style.display='table';
}
function setTicker(id, val) {
  const e=document.getElementById(id);
  if(e){ e.classList.remove('pending'); e.textContent=val; }
}

// ── Kill chart ───────────────────────────────────────
function kill(id) { if(_CH[id]){ _CH[id].destroy(); delete _CH[id]; } }

// ── Bar chart ────────────────────────────────────────
function mkBar(id, labels, data, horiz=false, color=null) {
  kill(id);
  const ctx=document.getElementById(id); if(!ctx) return;
  const PAL=['#00e0e0','#a060e0','#f0a030','#4080f0','#f06060','#00c8a0','#e060a0','#60a0f0'];
  const opts=baseOpts();
  if(horiz) opts.indexAxis='y';
  opts.scales.y.ticks.maxTicksLimit = horiz ? 15 : 6;
  _CH[id] = new Chart(ctx, {
    type:'bar',
    data:{ labels, datasets:[{ data, backgroundColor: color ? Array(data.length).fill(color) : labels.map((_,i)=>PAL[i%PAL.length]+'b0'), borderRadius:1, borderSkipped:false }] },
    options: opts,
  });
}

// ── Donut chart ──────────────────────────────────────
function mkDonut(id, labels, data, legId, cols=null) {
  kill(id);
  const ctx=document.getElementById(id); if(!ctx) return;
  const PAL=['#00e0e0','#a060e0','#f0a030','#4080f0','#f06060','#00c8a0','#e060a0','#60a0f0'];
  const total=data.reduce((a,b)=>a+b,0);
  const colors=cols||labels.map((_,i)=>PAL[i%PAL.length]);
  const c=getThemeColors();
  _CH[id] = new Chart(ctx, {
    type:'doughnut',
    data:{ labels, datasets:[{ data, backgroundColor:colors, borderWidth:3, borderColor:c.border, hoverOffset:3 }] },
    options:{
      responsive:true, cutout:'74%', animation:{duration:500},
      plugins:{ legend:{display:false}, tooltip:{
        backgroundColor:c.ttbg, borderColor:c.ttbrd, borderWidth:1,
        titleColor:c.tttxt, bodyColor:c.ttmut,
        titleFont:{family:"'Syne'",weight:'700',size:12},
        bodyFont:{family:"'DM Mono'",size:11},
        padding:10, cornerRadius:2,
        callbacks:{ label: x=>' '+Number(x.raw).toLocaleString('pt-BR')+' ('+(x.raw/total*100).toFixed(1)+'%)' }
      }}
    }
  });
  const leg=document.getElementById(legId);
  if(leg) leg.innerHTML=labels.map((l,i)=>`
    <div class="dleg-row">
      <div class="dleg-l"><div class="dleg-dot" style="background:${colors[i]}"></div><span>${l}</span></div>
      <span class="dleg-v">${Number(data[i]).toLocaleString('pt-BR')}</span>
    </div>`).join('');
}

// ── Line chart ───────────────────────────────────────
/**
 * mkLine(id, labels, datasets, legId?)
 *
 * datasets: array de objetos { label, data, color? }
 * legId:    id do elemento onde renderizar legenda (opcional)
 *
 * Exemplo — uma série:
 *   mkLine('c-evo', ['2020','2021','2022','2023','2024'],
 *          [{ label:'Matrículas', data:[...] }])
 *
 * Exemplo — múltiplas séries:
 *   mkLine('c-evo', anos,
 *          [{ label:'Matrículas', data:[...] },
 *           { label:'Ingressantes', data:[...], color:'#a060e0' },
 *           { label:'Concluintes', data:[...], color:'#f0a030' }],
 *          'leg-evo')
 */
function mkLine(id, labels, datasets, legId=null) {
  kill(id);
  const ctx = document.getElementById(id); if (!ctx) return;
  const PAL = ['#00e0e0','#a060e0','#f0a030','#4080f0','#f06060','#00c8a0'];
  const c   = getThemeColors();

  const chartDatasets = datasets.map((ds, i) => {
    const color = ds.color || PAL[i % PAL.length];
    return {
      label:           ds.label,
      data:            ds.data,
      borderColor:     color,
      backgroundColor: color + '18',
      pointBackgroundColor: color,
      pointRadius:     4,
      pointHoverRadius:6,
      borderWidth:     2,
      tension:         0.35,
      fill:            datasets.length === 1, // área só quando série única
    };
  });

  const opts = baseOpts();
  // tooltip multi-série
  opts.plugins.tooltip.callbacks = {
    label: x => `  ${x.dataset.label}: ${Number(x.raw).toLocaleString('pt-BR')}`,
  };
  // legenda nativa apenas quando legId não fornecido e há >1 série
  if (!legId && datasets.length > 1) {
    opts.plugins.legend = {
      display: true,
      labels: { color: c.tick, font: { family:"'DM Mono'", size:11 }, boxWidth:12, padding:16 },
    };
  }
  opts.scales.y.ticks.callback = v => fmtK(v);

  _CH[id] = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets: chartDatasets },
    options: opts,
  });

  // Legenda manual (mesmo padrão dos donuts)
  if (legId) {
    const leg = document.getElementById(legId);
    if (leg) leg.innerHTML = datasets.map((ds, i) => {
      const color = ds.color || PAL[i % PAL.length];
      const last  = ds.data[ds.data.length - 1] ?? 0;
      return `
        <div class="dleg-row">
          <div class="dleg-l">
            <div class="dleg-dot" style="background:${color}"></div>
            <span>${ds.label}</span>
          </div>
          <span class="dleg-v">${fmtK(last)}</span>
        </div>`;
    }).join('');
  }
}

// ── Theme update for existing charts ────────────────
document.getElementById('themeBtn')?.addEventListener('click', () => {
  setTimeout(() => {
    const c = getThemeColors();
    Object.values(_CH).forEach(ch => {
      ['x','y'].forEach(ax => {
        if(ch.options?.scales?.[ax]){
          ch.options.scales[ax].ticks.color  = c.tick;
          ch.options.scales[ax].grid.color   = c.grid;
          ch.options.scales[ax].border.color = c.grid;
        }
      });
      if(ch.options?.plugins?.tooltip) Object.assign(ch.options.plugins.tooltip, { backgroundColor:c.ttbg, borderColor:c.ttbrd, titleColor:c.tttxt, bodyColor:c.ttmut });
      ch.update('none');
    });
  }, 50);
});