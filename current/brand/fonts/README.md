# Fonts

`BricolageGrotesque-SemiBold.ttf` is the static SemiBold (600) instance of
[Bricolage Grotesque](https://fonts.google.com/specimen/Bricolage+Grotesque),
fetched from Google Fonts. It is licensed under the
[SIL Open Font License 1.1](https://openfontlicense.org/), which permits
redistribution alongside this project.

It is a **build-time dependency only**: `brand/build-assets.mts` reads the real
glyph outlines from it to construct the wordmark and to measure the t-crossbar.
Nothing here ships to the browser — the runtime webfonts come from the
`@fontsource-variable/*` packages, so the app works offline.

To refresh it:

```sh
UA="Mozilla/5.0 (Linux; U; Android 4.0.3; en-us)"
URL=$(curl -sS -A "$UA" \
  "https://fonts.googleapis.com/css?family=Bricolage+Grotesque:600" \
  | grep -o 'https://fonts.gstatic.com[^)]*' | head -1)
curl -sS -o BricolageGrotesque-SemiBold.ttf "$URL"
npm run brand:build
```
