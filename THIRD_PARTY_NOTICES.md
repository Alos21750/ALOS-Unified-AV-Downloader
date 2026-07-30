# Third-party notices

## Optional local subtitle-translation model pack

The optional `Jable_local_translation_v1.zip` archive contains converted,
quantized copies of the following third-party model checkpoints:

| Component | Immutable source revision | License |
| --- | --- | --- |
| `staka/fugumt-ja-en` | `f7ce11286e1fb7a8e1f1692ff3ab68c0f9c3aecb` | CC BY-SA 4.0 |
| `Helsinki-NLP/opus-mt-en-zh` | `408d9bc410a388e1d9aef112a2daba955b945255` | Apache License 2.0 |

Source model pages:

- <https://huggingface.co/staka/fugumt-ja-en/tree/f7ce11286e1fb7a8e1f1692ff3ab68c0f9c3aecb>
- <https://huggingface.co/Helsinki-NLP/opus-mt-en-zh/tree/408d9bc410a388e1d9aef112a2daba955b945255>

The checkpoints are converted to the CTranslate2 format and weight-quantized
to INT8. They are not fine-tuned or otherwise trained by this project. The
archive preserves each upstream model card, includes the Apache License 2.0
text plus the FuguMT creator/source/change notice and CC BY-SA 4.0 legal-code
links, and records source revisions and per-file SHA-256 hashes in
`manifest.json`. The converted FuguMT model files remain under CC BY-SA 4.0;
the OPUS-MT model remains under Apache 2.0.

CTranslate2 is an MIT-licensed conversion and inference runtime:
<https://github.com/OpenNMT/CTranslate2>.

SentencePiece is an Apache-2.0-licensed tokenizer runtime:
<https://github.com/google/sentencepiece>.

OpenCC and the bundled pure-Python `opencc-python-reimplemented` distribution
are Apache-2.0 licensed:
<https://github.com/BYVoid/OpenCC> and
<https://github.com/yichen0831/opencc-python>.

The bundled CTranslate2 Windows runtime includes Intel OpenMP
`libiomp5md.dll`. Intel permits redistribution of the relevant oneAPI runtime
components under the Intel Simplified Software License. The executable bundles
the complete applicable notice and terms at
`third_party_licenses/Intel-Simplified-Software-License.txt`. The Windows
release workflow disables UPX for all collected binaries. In particular,
`libiomp5md.dll` is redistributed without UPX transformation.

Windows executables are packaged with PyInstaller 6.13.0. The release workflow
builds its bootloader from the corresponding source distribution. PyInstaller
is licensed under GPL-2.0-or-later with a bootloader exception:
<https://github.com/pyinstaller/pyinstaller/blob/v6.13.0/COPYING.txt>.

CTranslate2 imports NumPy and PyYAML at runtime. The Windows executable pins
and bundles NumPy 2.5.1 under its BSD-3-Clause license and PyYAML 6.0.3 under
its MIT license. NumPy's wheel metadata, including the notices for its bundled
OpenBLAS/LAPACK/GCC runtime components, and PyYAML's license metadata are
included intact in the executable.

- NumPy: <https://github.com/numpy/numpy>
- PyYAML: <https://github.com/yaml/pyyaml>
- Intel Simplified Software License:
  <https://www.intel.com/content/www/us/en/content-details/749362/intel-simplified-software-license-version-october-2022.html>

### CTranslate2 MIT notice

> MIT License
> Copyright (c) 2018- SYSTRAN.
> Copyright (c) 2019- The OpenNMT Authors.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in
> all copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.

The full Apache License 2.0 text is available in [`LICENSE`](./LICENSE).
FuguMT attribution and modification details are available in
[`third_party_licenses/FuguMT-CC-BY-SA-4.0-NOTICE.txt`](./third_party_licenses/FuguMT-CC-BY-SA-4.0-NOTICE.txt).

The model pack is an optional download and is not part of the source archive.
Its models remain subject to their respective third-party license and model
card terms.
