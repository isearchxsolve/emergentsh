"""
AgentWorker — QThread wrapper around NIMAgentCore.

The worker lives in a background thread and runs the agentic loop.  All
UI updates happen through :class:`~src.core.signals.AgentSignals` which
Qt marshals to the GUI thread via queued connections.

Usage
-----
.. code-block:: python

    signals = AgentSignals()
    worker = AgentWorker(profile, project_dir, signals, prompt)
    worker.signals.token_content.connect(my_label.setText)
    worker.start()
"""

import time

from PySide6.QtCore import QThread

from ..core.agent_core import NIMAgentCore
from ..core.config import ConfigManager
from ..core.signals import AgentSignals


class AgentWorker(QThread):
    """
    Background thread that executes the agentic loop.

    Parameters
    ----------
    profile : dict
        Profile dict from ConfigManager.
    project_dir : str
        Working directory for file/shell tools.
    signals : AgentSignals
        Pre-created signal object (so the UI can connect before start).
    prompt : str
        The user's prompt for this run.
    resume : bool
        If True, attempt to load a saved session before running.
    """

    def __init__(
        self,
        profile: dict,
        project_dir: str,
        signals: AgentSignals,
        prompt: str,
        resume: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.signals: AgentSignals = signals
        self._profile = profile
        self._project_dir = project_dir
        self._prompt = prompt
        self._resume = resume
        self._agent: NIMAgentCore | None = None

    # ------------------------------------------------------------------
    @property
    def agent(self) -> NIMAgentCore | None:
        """Expose the underlying agent core (for stop / status queries)."""
        return self._agent

    # ------------------------------------------------------------------
    def request_stop(self) -> None:
        """Politely ask the agent to stop after the current chunk."""
        if self._agent:
            self._agent.request_stop()

    # ------------------------------------------------------------------
    def run(self) -> None:
        """QThread entry point — runs in the background thread."""
        try:
            self._agent = NIMAgentCore(
                profile=self._profile,
                project_dir=self._project_dir,
                signals=self.signals,
            )
            self._agent._rebuild_system()

            if self._resume:
                self._agent.load_session()
                self._agent._rebuild_system()

            self._agent.run(self._prompt)
        except Exception as e:
            self.signals.error.emit(f"Worker crashed: {e}")
        finally:
            # Ensure agent_finished is always emitted so the UI can
            # re-enable its input controls.
            self.signals.agent_finished.emit()
