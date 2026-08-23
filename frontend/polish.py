import re

with open(r'C:\god_ai\emergentsh\frontend\src\app\page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update main container background
content = content.replace('bg-gradient-to-b from-dark-900 via-dark-900 to-dark-950', 'bg-mesh-dark relative overflow-hidden')

# 2. Update hero text
content = content.replace('text-5xl sm:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight', 'text-5xl sm:text-6xl lg:text-7xl font-bold text-white mb-6 leading-tight animate-reveal-up drop-shadow-[0_0_15px_rgba(255,255,255,0.3)]')

# 3. Update feature cards to have glassmorphism and float
content = content.replace('group p-6 bg-dark-900/50 border border-dark-700 rounded-2xl hover:border-primary-500/30 transition-all duration-300', 'group p-6 bg-dark-900/40 backdrop-blur-xl border border-white/5 rounded-2xl hover:border-primary-500/50 hover:shadow-glow-primary transition-all duration-500 hover:-translate-y-2')

# 4. Update primary button
content = content.replace('bg-gradient-to-r from-primary-600 to-primary-700 hover:from-primary-700 hover:to-primary-800 rounded-xl transition-all duration-200', 'bg-gradient-to-r from-primary-600 to-primary-500 hover:from-primary-500 hover:to-primary-400 rounded-xl transition-all duration-500 shadow-glow-primary hover:scale-105')

# 5. Add a floating animated blob in the background of hero
hero_blob = """
      {/* Hero Section */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[800px] bg-primary-500/20 rounded-full blur-[120px] animate-blob-spin mix-blend-screen pointer-events-none -z-10" />
      <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8">
"""
content = content.replace('      {/* Hero Section */}\n      <section className="relative pt-32 pb-20 px-4 sm:px-6 lg:px-8">', hero_blob)

# 6. Update agent team cards
content = content.replace('p-6 bg-dark-900/50 border border-dark-700 rounded-2xl hover:border-primary-500/30 transition-all duration-300', 'p-6 bg-dark-900/30 backdrop-blur-lg border border-white/10 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] rounded-2xl hover:border-primary-500/50 hover:shadow-glow-primary transition-all duration-500 transform hover:scale-[1.03]')


with open(r'C:\god_ai\emergentsh\frontend\src\app\page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('UI Polished successfully.')
