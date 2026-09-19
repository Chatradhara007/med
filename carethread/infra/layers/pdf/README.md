# PDF render layer

Attached to `RasteriseFn` only, so the other functions stay small.

`pypdfium2` ships the PDFium engine inside the wheel: no poppler, no system
packages, no container image. It is permissively licensed, which PyMuPDF is
not.

## Building

```bash
cd carethread/infra
sam build --use-container      # required on macOS and Windows
```

`--use-container` builds inside the Lambda image so the manylinux wheel is
packaged. Without it, SAM installs the wheel for your own platform and the
function fails at import with a missing shared object.

## Verifying after deploy

Upload a PDF and watch the document status. `rasterising -> classifying` means
the layer works. A status of `failed` with "No PDF renderer is available in
this runtime" means the layer is missing or was built for the wrong platform.

## Fallbacks

`carethread/pipeline/rasterise/handler.py` tries pypdfium2, then PyMuPDF, then
pdf2image, and falls through on failure. Adding `pymupdf` here is enough to
switch engines; no code change is needed.
