# Upstream Baseline

KnowFlow Agent pins Hermes Agent `0.18.2`:

```text
tag: v2026.7.7.2
commit: 9de9c25f620ff7f1ce0fd5457d596052d5159596
license: MIT
```

The integration is an independent extension package. No Hermes core source is
copied into this repository. Any future upstream patch must be isolated under
`patches/`, documented with its reason and removal condition, and covered by a
regression test.
