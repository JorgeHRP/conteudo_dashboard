// ── Conteúdo Insights — charts.js ──────────────────
// Utilitários compartilhados de gráficos e formatação.
// Incluir após Chart.js em cada template de dashboard.

const _CH = {};

// ── Formatação ──────────────────────────────────────
const fmt  = n => Number(n).toLocaleString('pt-BR');
const fmtK = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(0)+'K' : String(n);
const pct  = (a,b) => b > 0 ? (a/b*100).toFixed(1)+'%' : '—';
const rCls = i => ['g','s','b'][i] || '';

// ── Theme ───────────────────────────────────────────
function getThemeColors() {
  const dark = document.documentElement.dataset.theme !== 'light';
  return dark
    ? { grid:'rgba(255,255,255,0.05)', tick:'#4a6070', ttbg:'#111820', ttbrd:'rgba(255,255,255,0.08)', tttxt:'#f0f4f8', ttmut:'#4a6070', border:'#0d1117' }
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
        titleFont: { family:"'IBM Plex Sans Condensed'", weight:'700', size:12 },
        bodyFont:  { family:"'IBM Plex Mono'", size:11 },
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

Chart.defaults.font.family = "'IBM Plex Mono', monospace";
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
  const PAL=['#a3e635','#22d3ee','#f59e0b','#a78bfa','#f87171','#34d399','#fb923c','#60a5fa'];
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
  const PAL=['#a3e635','#22d3ee','#f59e0b','#a78bfa','#f87171','#34d399','#fb923c','#60a5fa'];
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
        titleFont:{family:"'IBM Plex Sans Condensed'",weight:'700',size:12},
        bodyFont:{family:"'IBM Plex Mono'",size:11},
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
