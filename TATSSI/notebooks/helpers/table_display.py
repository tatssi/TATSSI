"""
Lightweight drop-in replacement for ``beakerx.TableDisplay``.

BeakerX is no longer maintained and has no build for Python >= 3.8, so the
Jupyter-notebook helpers cannot rely on it any more. This module provides a
minimal, API-compatible ``TableDisplay`` that:

  * is built from a pandas DataFrame,
  * renders the table in the notebook,
  * exposes a ``.values`` attribute (the underlying ``DataFrame.values``), and
  * supports ``setDoubleClickAction(callback)`` where ``callback`` has the
    beakerx signature ``callback(row, col, table)``.

Because plain Jupyter output cannot capture a real double click on a cell, the
"double click" is emulated with an ipywidgets row selector: choosing a row and
pressing the button invokes ``callback(row, last_col, self)`` — which is how the
TATSSI helpers use it (they read ``table.values[row][...]``).
"""

import pandas as pd

try:
    import ipywidgets as widgets
    from IPython.display import display, HTML
    _HAS_IPYWIDGETS = True
except Exception:  # pragma: no cover - notebooks only
    _HAS_IPYWIDGETS = False


class TableDisplay:
    """Minimal beakerx.TableDisplay replacement (see module docstring)."""

    def __init__(self, dataframe):
        if not isinstance(dataframe, pd.DataFrame):
            dataframe = pd.DataFrame(dataframe)
        self.df = dataframe.reset_index(drop=True)
        # beakerx exposes the raw values as a list of rows
        self.values = self.df.values
        self._double_click_action = None

    def setDoubleClickAction(self, callback):
        """Register a ``callback(row, col, table)`` (beakerx-compatible)."""
        self._double_click_action = callback

    def _trigger(self, row):
        if self._double_click_action is not None:
            last_col = max(0, self.df.shape[1] - 1)
            self._double_click_action(row, last_col, self)

    def _ipython_display_(self):
        if not _HAS_IPYWIDGETS:
            # Fallback: just show the table
            try:
                from IPython.display import display as _d
                _d(self.df)
            except Exception:
                print(self.df.to_string())
            return

        display(HTML(self.df.to_html(index=True, notebook=True)))

        if self._double_click_action is None:
            return

        # Emulate the double-click selection with a row picker + button
        row_selector = widgets.Dropdown(
            options=[(f"Row {i}", i) for i in range(self.df.shape[0])],
            value=0,
            description='Select row:',
            style={'description_width': 'initial'},
        )
        select_button = widgets.Button(
            description='Use selected row',
            tooltip='Apply the selected row (emulates beakerx double click)',
        )

        def _on_click(_b):
            self._trigger(row_selector.value)

        select_button.on_click(_on_click)
        display(widgets.HBox([row_selector, select_button]))
