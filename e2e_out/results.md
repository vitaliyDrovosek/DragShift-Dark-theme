# DragShift end-to-end test — 46/47 passed

| # | Where | Scenario | Result | Detail | Time |
|---|---|---|---|---|---|
| 1 | explorer | JPG → PNG | ✅ | Photo.png · 2400×1600 | 8.8s |
| 2 | explorer | JPG → WEBP | ✅ | Photo.webp · 2400×1600 | 5.4s |
| 3 | explorer | JPG → HEIC | ✅ | Photo.heic · 2400×1600 | 5.9s |
| 4 | explorer | JPG → TIFF | ✅ | Photo.tiff · 2400×1600 | 5.0s |
| 5 | explorer | JPG → AVIF | ✅ | Photo.avif · 2400×1600 | 5.4s |
| 6 | explorer | JPG → BMP | ✅ | Photo.bmp · 2400×1600 | 5.1s |
| 7 | explorer | JPG → PDF | ✅ | Photo.pdf · 1 page(s) | 5.1s |
| 8 | explorer | JPG → ICO | ✅ | Photo.ico · 128×86 | 5.1s |
| 9 | explorer | JPG → GIF | ✅ | Photo.gif · 2400×1600 | 5.3s |
| 10 | explorer | PNG → JPG | ✅ | Graphic.jpg · 800×533 | 5.0s |
| 11 | explorer | PDF → JPG (3 pages) | ✅ | 3 × .jpg | 5.1s |
| 12 | explorer | PDF → PNG (3 pages) | ✅ | 3 × .png | 6.4s |
| 13 | explorer | PDF → DOCX | ✅ | Report.docx | 5.1s |
| 14 | explorer | PDF → TXT | ✅ | Report.txt | 5.1s |
| 15 | explorer | DOCX → PDF | ✅ | Letter.pdf · 1 page(s) | 5.1s |
| 16 | explorer | DOCX → TXT | ✅ | Letter.txt | 5.1s |
| 17 | explorer | TXT → PDF | ✅ | Notes.pdf · 1 page(s) | 5.1s |
| 18 | explorer | TXT → DOCX | ✅ | Notes.docx | 5.1s |
| 19 | explorer | 2 images → 1 PDF | ✅ | 2 images → 2-page PDF | 6.6s |
| 20 | explorer | Compress to 200 KB | ✅ | 354 KB → 184 KB (48% smaller) | 10.1s |
| 21 | explorer | Resize 50% | ✅ | 2400×1600 → 1200×800 | 8.0s |
| 22 | explorer | Crop 1:1 | ✅ | 2400×1600 → 1600×1600 | 8.6s |
| 23 | explorer | Edit: auto + rotate | ✅ | 2400×1600 → 1600×2400 | 9.7s |
| 24 | explorer | Annotate | ✅ | Photo Annotated.jpg | 10.8s |
| 25 | explorer | Redact | ✅ | Photo Redacted.jpg · centre blacked out | 9.3s |
| 26 | explorer | Add BG 1:1 | ✅ | 2400×1600 → 2976×2976 | 10.6s |
| 27 | explorer | Metadata: remove location | ✅ | GPS removed, kept Apple iPhone 15 Pro | 7.5s |
| 28 | explorer | Metadata: remove all | ✅ | 0 metadata fields left | 7.4s |
| 29 | explorer | PDF Compress | ✅ | 227 KB → 108 KB | 6.0s |
| 30 | explorer | PDF Split | ✅ | 3 PDFs | 6.0s |
| 31 | explorer | PDF Rotate | ✅ | all pages at 90° | 6.0s |
| 32 | explorer | PDF Protect | ✅ | AES-256, password works | 9.0s |
| 33 | explorer | PDF Extract images | ✅ | 1 image(s) in Report images/ | 5.9s |
| 34 | explorer | PDF Metadata | ✅ | author/title removed | 7.4s |
| 35 | explorer | Merge 2 PDFs | ✅ | 5 pages | 7.5s |
| 36 | send-to | Send To → PNG | ✅ | Photo.png · 2400×1600 | 5.2s |
| 37 | explorer | Shift×2: JPG → PNG | ✅ | Photo.png · 2400×1600 | 5.3s |
| 38 | explorer | Shift×2 + Shift: PDF Rotate | ✅ | all pages at 90° | 5.4s |
| 39 | desktop | Desktop: JPG → PNG | ✅ | D-Photo.png · 2400×1600 | 5.5s |
| 40 | desktop | Desktop: PDF → TXT | ✅ | D-Report.txt | 4.9s |
| 41 | desktop | Desktop: DOCX → PDF | ✅ | D-Letter.pdf · 1 page(s) | 4.9s |
| 42 | desktop | Desktop: Compress | ✅ | 354 KB → 184 KB (48% smaller) | 9.7s |
| 43 | desktop | Desktop: Crop | ❌ | RuntimeError: window not found: Crop Image.* | 18.2s |
| 44 | desktop | Desktop: Add BG | ✅ | 800×533 → 992×992 | 8.9s |
| 45 | desktop | Desktop: 2 PDFs merge | ✅ | 5 pages | 7.1s |
| 46 | desktop | Desktop Shift×2: PDF → TXT | ✅ | D-Report.txt | 4.7s |
| 47 | all | Drag picture kept out of the glass | ✅ | menu doesn't capture the screen (solid dark background) | 0s |