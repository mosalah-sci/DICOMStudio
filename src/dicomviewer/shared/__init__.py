"""Cross-cutting helpers shared by every architectural layer.

Only leaf modules that depend on nothing inside the project may live here.
Anything used by a single layer belongs in that layer, not in this package.
"""
