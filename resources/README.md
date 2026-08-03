# Resources

Runtime assets that are bundled with the packaged application.

The actual files are shipped inside the `dicomviewer` package under
`src/dicomviewer/resources/` so the same files serve source-tree development
and the installed wheel (loaded through `importlib.resources`):

```
src/dicomviewer/resources/
├── icons/     application icons (single consistent SVG line-icon set)
└── styles/    Qt stylesheet themes (base template, tokenized per theme)
```

The `assets/` directory at the repository root is distinct: it holds
repository-only media that is never bundled.
