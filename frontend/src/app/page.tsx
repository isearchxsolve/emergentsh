'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Sparkles, Zap, Github, Database, Layers, Terminal, CheckCircle, Loader2 } from 'lucide-react';

const features = [
  { icon: Sparkles, title: 'Vibe Coding', desc: 'Describe your app in plain English - no code required' },
  { icon: Layers, title: 'Full-Stack Generation', desc: 'React frontend, FastAPI backend, PostgreSQL database' },
  { icon: Terminal, title: 'Live Preview', desc: 'See your app running as agents build it in real-time' },
  { icon: Github, title: 'GitHub Sync', desc: 'Export code, sync to GitHub with meaningful commits' },
  { icon: Database, title: 'Persistent Projects', desc: 'Projects, conversations, and artifacts survive restarts' },
  { icon: Zap, title: 'NVIDIA NIM Exclusive', desc: 'All inference powered by NVIDIA NIM endpoints' },
];

const steps = [
  { num: '01', title: 'Describe', desc: 'Type what you want to build in natural language' },
  { num: '02', title: 'Watch', desc: 'Multi-agent team plans, codes, tests, and deploys' },
  { num: '03', title: 'Preview', desc: 'Live preview updates as the app is built' },
  { num: '04', title: 'Iterate', desc: 'Chat to refine: "add dark mode", "fix login bug"' },
  { num: '05', title: 'Export', desc: 'Download code or deploy with one click' },
];

export default function HomePage() {
  const router = useRouter();
  const [prompt, setPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setIsLoading(true);
    // Navigate to the actual workspace
    router.push('/workspace');
  };

  return (
    <div className="min-h-screen bg-mesh-dark relative overflow-hidden">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-dark-950/80 backdrop-blur-md border-b border-dark-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                <Sparkles className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-white">Emergent</span>
            </div>
            <div className="hidden md:flex items-center gap-8">
              <a href="#features" className="text-dark-300 hover:text-white transition-colors">Features</a>
              <a href="#how-it-works" className="text-dark-300 hover:text-white transition-colors">How It Works</a>
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-dark-300 hover:text-white transition-colors">GitHub</a>
            </div>
            <div className="flex items-center gap-4">
              <button className="hidden sm:block px-4 py-2 text-sm font-medium text-dark-300 hover:text-white transition-colors">
                Sign In
              </button>
              <button onClick={() => router.push('/workspace')} className="px-4 py-2 text-sm font-medium text-white bg-primary-600 hover:bg-primary-700 rounded-lg transition-colors">
                Start Building
              </button>
            </div>
          </div>
        </div>
      </nav>


      {/* Hero Section */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-primary-500/20 rounded-full blur-[120px] animate-blob-spin mix-blend-screen pointer-events-none -z-10" />
      <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8">

        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary-500/10 border border-primary-500/20 text-primary-400 text-sm mb-8">
            <span className="w-2 h-2 bg-primary-500 rounded-full animate-pulse"></span>
            Powered by NVIDIA NIM • Exclusive Inference Engine
          </div>
          <h1 className="text-5xl sm:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight animate-reveal-up drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]">
            Describe your idea{' '}
            <span className="bg-gradient-to-r from-primary-400 via-primary-500 to-primary-600 bg-clip-text text-transparent">
              → Build websites & apps with AI
            </span>
          </h1>
          <p className="text-xl sm:text-2xl text-dark-300 mb-10 max-w-3xl mx-auto leading-relaxed">
            The world&apos;s first truly agentic vibe coding platform. A multi-agent team powered
            exclusively by NVIDIA NIM plans, codes, tests, and deploys production-ready full-stack applications.
          </p>
          
          {/* Prompt Input */}
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto mb-16">
            <div className="relative">
              <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 to-primary-600/10 rounded-2xl blur-2xl -z-10"></div>
              <div className="relative bg-dark-950/80 backdrop-blur-md border border-dark-700 rounded-2xl p-2">
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="e.g. Build a SaaS task manager with user auth, Stripe billing, and a dashboard"
                  className="w-full bg-transparent text-white placeholder-dark-500 text-lg py-6 px-6 resize-none focus:outline-none min-h-[100px]"
                  rows={3}
                  disabled={isLoading}
                />
              </div>
            </div>
            <div className="mt-4 flex justify-center">
              <button
                type="submit"
                disabled={isLoading || !prompt.trim()}
                className="group w-full sm:w-auto px-8 py-4 text-lg font-medium text-white bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 rounded-xl transition-all duration-500 shadow-glow-primary hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-6 h-6 animate-spin" />
                    Building your app...
                  </>
                ) : (
                  <>
                    <span>Start Building</span>
                    <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                  </>
                )}
              </button>
            </div>
            <p className="text-center text-dark-500 mt-4 text-sm">
              No credit card required • Powered by NVIDIA NIM • Free tier available
            </p>
          </form>

          {/* Example Prompts */}
          <div className="flex flex-wrap justify-center gap-3 mb-16">
            {[
              'SaaS task manager with auth & billing',
              'E-commerce store with cart & payments',
              'Real-time chat app with rooms',
              'Project management with kanban board',
            ].map((example) => (
              <button
                key={example}
                onClick={() => setPrompt(example)}
                className="px-4 py-2 text-sm text-dark-300 bg-dark-800/50 border border-dark-700 hover:border-primary-500/50 hover:text-white rounded-lg transition-all"
              >
                {example}
              </button>
            ))}
          </div>

          {/* Trust Indicators */}
          <div className="flex items-center justify-center gap-8 text-dark-500 text-sm">
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>NVIDIA NIM Exclusive</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>Open Source</span>
            </div>
            <div className="flex items-center gap-2">
              <CheckCircle className="w-4 h-4 text-green-500" />
              <span>Production Ready</span>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-20 px-4 sm:px-6 lg:px-8 bg-dark-950/50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">Why Emergent?</h2>
            <p className="text-xl text-dark-400 max-w-2xl mx-auto">
              Unlike no-code tools, Emergent generates real, executable code you own.
              Every component is production-ready from day one.
            </p>
          </div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <div
                key={feature.title}
                className="group p-6 bg-dark-900/40 backdrop-blur-xl border border-white/5 rounded-2xl hover:border-primary-500/50 hover:shadow-glow-primary transition-all duration-500 hover:-translate-y-2"
              >
                <div className="w-12 h-12 bg-primary-500/10 rounded-xl flex items-center justify-center mb-4 group-hover:bg-primary-500/20 transition-colors">
                  <feature.icon className="w-6 h-6 text-primary-400" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-2">{feature.title}</h3>
                <p className="text-dark-400">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section id="how-it-works" className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">How It Works</h2>
            <p className="text-xl text-dark-400 max-w-2xl mx-auto">
              From idea to deployed app in minutes, not months.
            </p>
          </div>
          <div className="grid md:grid-cols-5 gap-4">
            {steps.map((step, index) => (
              <div key={step.num} className="relative">
                <div className="w-14 h-14 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl flex items-center justify-center text-2xl font-bold text-white mb-4">
                  {step.num}
                </div>
                <h3 className="text-lg font-semibold text-white mb-1">{step.title}</h3>
                <p className="text-dark-400 text-sm">{step.desc}</p>
                {index < steps.length - 1 && (
                  <div className="absolute top-7 right-[-12%] hidden md:block w-[24%] h-0.5 bg-gradient-to-r from-primary-500 to-transparent" />
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Agent Team Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-dark-950/50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-white mb-4">Your AI Agent Team</h2>
            <p className="text-xl text-dark-400 max-w-2xl mx-auto">
              Specialized agents collaborate like a real engineering team.
            </p>
          </div>
          <div className="grid md:grid-cols-4 gap-6">
            {[
              { name: 'Orchestrator', role: 'Plans architecture & task breakdown', color: 'from-purple-500 to-purple-700' },
              { name: 'Frontend', role: 'React/Next.js components & UI', color: 'from-blue-500 to-blue-700' },
              { name: 'Backend', role: 'FastAPI/Node APIs & business logic', color: 'from-green-500 to-green-700' },
              { name: 'Database', role: 'Schema, migrations & queries', color: 'from-amber-500 to-amber-700' },
              { name: 'Tester', role: 'Runs tests, detects & fixes failures', color: 'from-red-500 to-red-700' },
              { name: 'Deployer', role: 'Live preview & deployable artifacts', color: 'from-cyan-500 to-cyan-700' },
            ].map((agent, index) => (
              <div
                key={agent.name}
                className="p-6 bg-dark-900/30 backdrop-blur-lg border border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] rounded-2xl hover:border-primary-500/50 hover:shadow-glow-primary transition-all duration-500 transform hover:scale-[1.03]"
              >
                <div className={`w-12 h-12 bg-gradient-to-br ${agent.color} rounded-xl flex items-center justify-center mb-4`}>
                  <Terminal className="w-6 h-6 text-white" />
                </div>
                <h3 className="text-xl font-semibold text-white mb-1">{agent.name}</h3>
                <p className="text-dark-400">{agent.role}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto text-center">
          <div className="relative">
            <div className="absolute inset-0 bg-gradient-to-r from-primary-500/10 to-primary-600/10 rounded-3xl blur-2xl -z-10"></div>
            <div className="relative bg-dark-950/80 backdrop-blur-md border border-dark-700 rounded-3xl p-10 md:p-16">
              <h2 className="text-4xl font-bold text-white mb-4">
                Ready to build your app?
              </h2>
              <p className="text-xl text-dark-400 mb-8">
                Join developers building production apps with AI agents.
              </p>
              <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-4 justify-center max-w-md mx-auto">
                <input
                  type="text"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="What do you want to build?"
                  className="flex-1 bg-dark-900 border border-dark-700 text-white placeholder-dark-500 px-6 py-4 rounded-xl focus:outline-none focus:border-primary-500"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={isLoading || !prompt.trim()}
                  className="px-8 py-4 text-lg font-medium text-white bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 rounded-xl transition-all duration-500 shadow-glow-primary hover:scale-105 disabled:opacity-50 flex items-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-6 h-6 animate-spin" />
                      Building...
                    </>
                  ) : (
                    <>
                      Start Building
                      <ArrowRight className="w-5 h-5" />
                    </>
                  )}
                </button>
              </form>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 px-4 sm:px-6 lg:px-8 border-t border-dark-800">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-4 gap-8 mb-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-8 h-8 bg-gradient-to-br from-primary-500 to-primary-700 rounded-lg flex items-center justify-center">
                  <Sparkles className="w-5 h-5 text-white" />
                </div>
                <span className="text-xl font-bold text-white">Emergent</span>
              </div>
              <p className="text-dark-400 text-sm">
                Build production-ready full-stack applications with AI agents powered by NVIDIA NIM.
              </p>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Product</h4>
              <ul className="space-y-2 text-dark-400 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Features</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Pricing</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Documentation</a></li>
                <li><a href="#" className="hover:text-white transition-colors">API Reference</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Company</h4>
              <ul className="space-y-2 text-dark-400 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">About</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Blog</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Careers</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Contact</a></li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-white mb-4">Legal</h4>
              <ul className="space-y-2 text-dark-400 text-sm">
                <li><a href="#" className="hover:text-white transition-colors">Privacy</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Terms</a></li>
                <li><a href="#" className="hover:text-white transition-colors">Security</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-dark-800 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-dark-500 text-sm">
              © 2024 Emergent. Built with NVIDIA NIM.
            </p>
            <div className="flex items-center gap-4">
              <a href="https://github.com" target="_blank" rel="noopener noreferrer" className="text-dark-400 hover:text-white transition-colors">
                <Github className="w-5 h-5" />
              </a>
              <a href="https://twitter.com" target="_blank" rel="noopener noreferrer" className="text-dark-400 hover:text-white transition-colors">
                <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M23 3a10.9 10.9 0 0 1-3.14 1.53 4.48 4.48 0 0 0-7.86 3v1A10.66 10.66 0 0 1 3 4s-4 9 5 13a11.64 11.64 0 0 1-7 2c9 5 20 0 20-11.5a4.5 4.5 0 0 0-.08-.83A7.72 7.72 0 0 0 23 3z"></path></svg>
              </a>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}