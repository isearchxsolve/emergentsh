'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Blocks, Bot, Check, ChevronRight, Code2, Github, Layers3, Loader2, Play, ShieldCheck, Sparkles, WandSparkles, Zap } from 'lucide-react';

const agents = [
  { name: 'Planner', color: 'bg-violet-400', state: 'Architecture ready' },
  { name: 'Designer', color: 'bg-fuchsia-400', state: 'Design system crafted' },
  { name: 'Frontend', color: 'bg-cyan-400', state: 'Building interface' },
  { name: 'Backend', color: 'bg-emerald-400', state: 'API connected' },
];

const capabilities = [
  { icon: WandSparkles, title: 'Idea to interface', text: 'Describe the product. NeonBuild supplies the production baseline automatically.' },
  { icon: Blocks, title: 'A real full stack', text: 'Frontend, API, data model, validation, tests, and runnable artifacts move together.' },
  { icon: ShieldCheck, title: 'Self-correcting loops', text: 'Agents diagnose failures, repair the artifact, and test again before calling it done.' },
];

export default function HomePage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const launch = (event: React.FormEvent) => {
    event.preventDefault();
    if (!prompt.trim()) return;
    setIsLoading(true);
    router.push('/workspace');
  };

  return (
    <main className="min-h-screen overflow-hidden bg-[#05060a] text-white selection:bg-cyan-400/30">
      <div className="pointer-events-none fixed inset-0 aurora-canvas" />
      <div className="pointer-events-none fixed inset-0 bg-grid-fade opacity-50" />

      <nav className="fixed inset-x-0 top-0 z-50 px-4 pt-4">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between rounded-2xl border border-white/[0.08] bg-[#0a0c13]/70 px-4 shadow-2xl shadow-black/30 backdrop-blur-2xl sm:px-6">
          <button onClick={() => router.push('/')} className="group flex items-center gap-3" aria-label="NeonBuild home">
            <span className="relative grid h-9 w-9 place-items-center overflow-hidden rounded-xl bg-gradient-to-br from-cyan-300 via-blue-500 to-violet-600 shadow-[0_0_28px_rgba(34,211,238,.28)]"><Sparkles className="h-5 w-5" /></span>
            <span className="text-lg font-semibold tracking-[-0.03em]">Neon<span className="text-cyan-300">Build</span></span>
          </button>
          <div className="hidden items-center gap-8 text-sm text-slate-400 md:flex">
            <a href="#capabilities" className="transition-colors hover:text-white">Capabilities</a>
            <a href="#workflow" className="transition-colors hover:text-white">How it works</a>
            <a href="https://github.com" target="_blank" rel="noreferrer" className="flex items-center gap-2 transition-colors hover:text-white"><Github className="h-4 w-4" /> GitHub</a>
          </div>
          <button onClick={() => router.push('/workspace')} className="group flex items-center gap-2 rounded-xl border border-cyan-300/20 bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 shadow-[0_0_24px_rgba(34,211,238,.2)] transition hover:-translate-y-0.5 hover:bg-white">Open studio <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></button>
        </div>
      </nav>

      <section className="relative mx-auto grid min-h-screen max-w-7xl items-center gap-16 px-6 pb-20 pt-36 lg:grid-cols-[.92fr_1.08fr] lg:px-8">
        <div className="relative z-10">
          <div className="mb-7 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/[0.06] px-3 py-1.5 text-xs font-medium text-cyan-100 backdrop-blur-xl"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-300 opacity-50" /><span className="relative h-2 w-2 rounded-full bg-emerald-300" /></span>NVIDIA NIM live · multi-agent build system</div>
          <h1 className="max-w-3xl text-5xl font-semibold leading-[.98] tracking-[-0.055em] text-balance sm:text-6xl xl:text-[5.35rem]">Your idea deserves a<span className="block bg-gradient-to-r from-white via-cyan-200 to-violet-300 bg-clip-text text-transparent">world-class build.</span></h1>
          <p className="mt-7 max-w-xl text-lg leading-8 text-slate-400 sm:text-xl">Tell NeonBuild what you want to create. A coordinated AI team plans, designs, codes, tests, repairs, and previews the product with you.</p>

          <form onSubmit={launch} className="mt-10 max-w-2xl">
            <div className="prompt-shell group relative rounded-[1.6rem] p-px">
              <div className="relative rounded-[calc(1.6rem-1px)] bg-[#090b12]/90 p-3 backdrop-blur-2xl">
                <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={3} disabled={isLoading} placeholder="Build a beautiful project hub for a creative studio…" className="min-h-28 w-full resize-none bg-transparent px-4 py-3 text-lg leading-7 text-white outline-none placeholder:text-slate-600" />
                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] px-2 pt-3">
                  <div className="flex items-center gap-2 text-xs text-slate-500"><Bot className="h-4 w-4 text-violet-300" /> Production defaults included</div>
                  <button disabled={isLoading || !prompt.trim()} className="group flex items-center gap-2 rounded-xl bg-gradient-to-r from-cyan-300 to-blue-400 px-5 py-2.5 text-sm font-semibold text-slate-950 shadow-[0_0_26px_rgba(34,211,238,.2)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40">{isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4 fill-current" />}Build it <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" /></button>
                </div>
              </div>
            </div>
          </form>
          <div className="mt-5 flex flex-wrap gap-2">{['Creative agency hub', 'AI research dashboard', 'Premium client portal'].map((idea) => <button key={idea} onClick={() => setPrompt(idea)} className="rounded-full border border-white/[0.07] bg-white/[0.035] px-3 py-1.5 text-xs text-slate-400 transition hover:border-cyan-300/20 hover:bg-cyan-300/[0.05] hover:text-cyan-100">{idea}</button>)}</div>
        </div>

        <div className="relative hidden min-h-[610px] lg:block">
          <div className="absolute inset-0 rounded-full bg-blue-500/10 blur-[100px]" />
          <div className="absolute left-5 top-12 w-[94%] rotate-[1.5deg] rounded-[2rem] border border-white/[0.08] bg-white/[0.025] p-3 shadow-[0_40px_120px_rgba(0,0,0,.55)] backdrop-blur-2xl">
            <div className="overflow-hidden rounded-[1.45rem] border border-white/[0.08] bg-[#080a10]/95">
              <div className="flex h-14 items-center justify-between border-b border-white/[0.07] px-5"><div className="flex items-center gap-3"><div className="flex gap-1.5"><i className="h-2.5 w-2.5 rounded-full bg-red-400/70" /><i className="h-2.5 w-2.5 rounded-full bg-amber-300/70" /><i className="h-2.5 w-2.5 rounded-full bg-emerald-300/70" /></div><span className="text-xs text-slate-500">Luma · Project workspace</span></div><span className="flex items-center gap-2 rounded-full bg-emerald-300/[0.08] px-2.5 py-1 text-[10px] text-emerald-200"><span className="h-1.5 w-1.5 rounded-full bg-emerald-300" /> Live preview</span></div>
              <div className="grid h-[470px] grid-cols-[150px_1fr]">
                <div className="border-r border-white/[0.06] p-4"><div className="mb-7 flex items-center gap-2 text-xs font-medium"><span className="grid h-7 w-7 place-items-center rounded-lg bg-violet-400/15 text-violet-200"><Layers3 className="h-3.5 w-3.5" /></span> Agent flow</div><div className="space-y-5">{agents.map((agent, index) => <div key={agent.name} className="relative flex gap-2.5"><span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${agent.color} ${index === 2 ? 'animate-pulse' : ''}`} />{index < agents.length - 1 && <span className="absolute left-[3px] top-4 h-6 w-px bg-white/10" />}<div><p className="text-[11px] text-slate-200">{agent.name}</p><p className="mt-0.5 text-[8px] leading-3 text-slate-600">{agent.state}</p></div></div>)}</div></div>
                <div className="relative overflow-hidden bg-gradient-to-br from-[#0c1019] to-[#07090e] p-5">
                  <div className="mb-5 flex items-center justify-between"><div><p className="text-[10px] uppercase tracking-[.2em] text-cyan-300/70">Live product</p><h3 className="mt-1 text-xl font-medium tracking-tight">Creative command center</h3></div><button className="grid h-8 w-8 place-items-center rounded-full border border-white/10 bg-white/5"><Play className="h-3 w-3 fill-white" /></button></div>
                  <div className="grid grid-cols-3 gap-3">{['24 active', '87% velocity', '6 shipping'].map((v, i) => <div key={v} className="rounded-xl border border-white/[0.07] bg-white/[0.035] p-3"><p className={`text-lg font-medium ${i === 0 ? 'text-cyan-200' : i === 1 ? 'text-violet-200' : 'text-emerald-200'}`}>{v.split(' ')[0]}</p><p className="mt-1 text-[9px] text-slate-500">{v.substring(v.indexOf(' ') + 1)}</p></div>)}</div>
                  <div className="mt-4 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-4"><div className="mb-4 flex items-center justify-between"><p className="text-xs text-slate-300">This week</p><p className="text-[9px] text-emerald-300">+18.4%</p></div><div className="flex h-28 items-end gap-2">{[36,54,42,75,62,88,72,96,78,105,92,116].map((h, i) => <span key={i} className="flex-1 rounded-t bg-gradient-to-t from-blue-600/40 to-cyan-300/80" style={{height:h}} />)}</div></div>
                  <div className="mt-4 grid grid-cols-2 gap-3"><div className="rounded-xl border border-violet-300/10 bg-violet-300/[0.035] p-3 text-[10px] text-slate-400">Next milestone<span className="mt-1 block text-sm text-white">Client beta</span></div><div className="rounded-xl border border-cyan-300/10 bg-cyan-300/[0.035] p-3 text-[10px] text-slate-400">Agent confidence<span className="mt-1 block text-sm text-white">98.6%</span></div></div>
                </div>
              </div>
            </div>
          </div>
          <div className="absolute -right-2 bottom-16 rounded-2xl border border-white/10 bg-[#0d1018]/85 p-4 shadow-2xl backdrop-blur-2xl animate-float"><div className="flex items-center gap-3"><span className="grid h-9 w-9 place-items-center rounded-xl bg-emerald-300/10 text-emerald-300"><Check className="h-4 w-4" /></span><div><p className="text-xs font-medium">QA passed</p><p className="mt-0.5 text-[10px] text-slate-500">42 checks · zero regressions</p></div></div></div>
        </div>
      </section>

      <section id="capabilities" className="relative mx-auto max-w-7xl px-6 py-24 lg:px-8">
        <div className="mb-12 max-w-2xl"><p className="text-xs font-semibold uppercase tracking-[.24em] text-cyan-300">Built into every project</p><h2 className="mt-4 text-4xl font-semibold tracking-[-.04em] sm:text-5xl">You bring the vision.<br/><span className="text-slate-500">The system brings the rigor.</span></h2></div>
        <div className="grid gap-4 md:grid-cols-3">{capabilities.map(({icon: Icon,title,text}, index) => <article key={title} className="glass-card group rounded-3xl p-7 transition duration-500 hover:-translate-y-1"><div className="mb-8 flex items-center justify-between"><span className={`grid h-12 w-12 place-items-center rounded-2xl ${index===0?'bg-violet-300/10 text-violet-200':index===1?'bg-cyan-300/10 text-cyan-200':'bg-emerald-300/10 text-emerald-200'}`}><Icon className="h-5 w-5" /></span><span className="text-xs text-slate-700">0{index+1}</span></div><h3 className="text-xl font-medium tracking-tight">{title}</h3><p className="mt-3 leading-7 text-slate-500">{text}</p><div className="mt-7 flex items-center gap-1 text-xs text-slate-400 transition group-hover:text-cyan-200">Included by default <ChevronRight className="h-3.5 w-3.5" /></div></article>)}</div>
      </section>

      <section id="workflow" className="relative mx-auto max-w-7xl px-6 pb-28 pt-14 lg:px-8"><div className="overflow-hidden rounded-[2.4rem] border border-white/[0.08] bg-gradient-to-br from-white/[0.055] to-white/[0.015] p-8 backdrop-blur-2xl sm:p-12"><div className="grid gap-12 lg:grid-cols-[.8fr_1.2fr] lg:items-center"><div><span className="inline-flex items-center gap-2 rounded-full bg-violet-300/10 px-3 py-1 text-xs text-violet-200"><Code2 className="h-3.5 w-3.5" /> Self-healing delivery</span><h2 className="mt-5 text-4xl font-semibold tracking-[-.04em]">Build. Test. Repair.<br/>Ship with confidence.</h2><p className="mt-5 max-w-lg leading-7 text-slate-400">Each specialist hands structured artifacts to the next. When validation fails, the failing code and exact error return to the responsible agent for another pass.</p></div><div className="grid gap-3 sm:grid-cols-2">{['Plan the product baseline','Craft the visual system','Generate the full stack','Validate and self-correct'].map((step,i)=><div key={step} className="flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-black/20 p-4"><span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-white/[0.05] text-xs text-cyan-200">{i+1}</span><span className="text-sm text-slate-300">{step}</span></div>)}</div></div></div></section>
      <footer className="relative border-t border-white/[0.06] px-6 py-8"><div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 text-xs text-slate-600 sm:flex-row"><span>NeonBuild · Intelligent software delivery</span><span>Powered by NVIDIA NIM</span></div></footer>
    </main>
  );
}
