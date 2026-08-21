"""vizbin -- format-agnostic binary visualization.

Take a blob. Pretend it is an image. Vary the lie until the truth starts to show.
"""

# Single source of truth for the version. pyproject.toml reads this via
# setuptools' dynamic `attr` (a static AST read -- no import, no runtime I/O),
# and the CLI's --version wires straight to it. Bump here and nowhere else.
__version__ = "0.4.0"
