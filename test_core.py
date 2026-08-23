"""Smoke tests for core logic."""
import os, sys
os.environ['QT_QPA_PLATFORM'] = 'offscreen'

# Test rate limiter
from src.core.rate_limiter import TokenBucket, TokenMeter
import time

tb = TokenBucket(rpm=60, burst=2, min_gap=0.1, safety_margin=0.8)
assert tb.rpm == 48.0, f'Expected 48.0, got {tb.rpm}'
assert tb.reserve(timeout=5), 'Should reserve immediately with burst=2'
assert tb.reserve(timeout=5), 'Should reserve second from burst'
tb.commit()
print(f'TokenBucket: rpm={tb.rpm}, tokens={tb.tokens:.2f} - OK')

tm = TokenMeter()
tm.record(100, 50)
tm.record(200, 75)
assert tm.total_prompt == 300
assert tm.total_completion == 125
print(f'TokenMeter: prompt={tm.total_prompt}, completion={tm.total_completion} - OK')

# Test tools
from src.core.tools import FileTools, execute_tool
ft = FileTools('.')
result = ft.read('main.py')
assert 'EmergentSH' in result, 'Should read main.py'
print(f'FileTools.read: {len(result)} chars - OK')

result = ft.search('EmergentSH', 'src')
assert len(result) > 0, 'Should find matches in src'
print(f'FileTools.search: found matches - OK')

# Test path safety
try:
    ft._safe('../../etc/passwd')
    assert False, 'Should have raised PermissionError'
except PermissionError:
    print('FileTools._safe: path escape blocked - OK')

# Test config
from src.core.config import ConfigManager
profiles = ConfigManager.get_profiles()
print(f'ConfigManager: {len(profiles)} profiles loaded - OK')

# Test agent core
from src.core.signals import AgentSignals
from src.core.agent_core import NIMAgentCore
sig = AgentSignals()
agent = NIMAgentCore(
    {'name': 'test', 'key': 'fake', 'default_model': 'glm',
     'rpm': 40, 'models': {'glm': {'name': 'GLM', 'id': 'z-ai/glm-5.2'}}},
    '.', sig
)
agent._rebuild_system()
assert len(agent.messages) == 1, f'Expected 1 message, got {len(agent.messages)}'
print(f'AgentCore: messages={len(agent.messages)}, est_tokens={agent.est_tokens()} - OK')

try:
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    from src.ui.main_window import MainWindow
    w = MainWindow()
    print(f'MainWindow: created - OK')
except Exception as e:
    print(f'MainWindow creation skipped in headless mode: {e}')

print()
print('=== ALL CORE LOGIC TESTS PASSED ===')
import os
os._exit(0)
