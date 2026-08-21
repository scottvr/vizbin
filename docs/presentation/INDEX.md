### ** 11-Slide Deck Structure**

#### **Slide 1: Title Slide — Vizbin: A Visual Guide to Binary Discovery**
*   **Focus**: Hook the audience with the project's central philosophy: *"Take a blob. Pretend it is an image. Vary the lie until the truth starts to show."*
*   **Context**: Zero-dependency visual reverse-engineering.

#### **Slide 2: The Reverse Engineer's Blind Spot**
*   **Focus**: Reversing unknown binaries usually starts with a struggle—writing ad-hoc parsers, looking at disassembler static, or dumping strings. 
*   **Vizbin's Alternative**: Perform instant reconnaissance without inferring file formats, running parsers, or consulting schemas. Just raw bytes on a canvas.

#### **Slide 3: Hypothesis-Driven Reversing**
*   **Focus**: Explain that visual exploration is actually a series of testing hypotheses.
    *   **Width** is a hypothesis about *periodicity* (record sizes, page boundaries, strides).
    *   **Projection** is a hypothesis about *which byte properties matter*.
    *   **Offset** is a hypothesis about *structural origin and phase*.

#### **Slide 4: Knob #1 — Tuning the Stride (Width & Animation)**
*   **Focus**: Demonstrate how wrapping bytes at the wrong width smears structure, while the right width locks it into place. 
*   **Features**: Showcase **"visual stride spectroscopy"** using `vizbin suggest` to rank adjacent-row coherence and `vizbin animate` to sweep widths dynamically, letting structure snap into alignment.

#### **Slide 5: Knob #2 — Changing your Lenses (Projections)**
*   **Focus**: Walk through the specialized "instruments" available:
    *   `gray`: Byte values for fine textures and padding.
    *   `byteclass`: Separates nulls, printables, and high-bits.
    *   `entropy`: Highlights transitions between code, padding, and compressed payloads.
    *   `delta`: Exposes slow ramps and counters.
    *   **Text Mode**: A visual strings tool that prints readable ASCII glyphs in-line while keeping the surrounding binary scaffolding visible.

#### **Slide 6: Advanced Composition (Depth vs. Breadth)**
*   **Focus**: How to ask complex, multi-layered questions:
    *   **Depth**: Chaining transforms in series (e.g., `-t xor,entropy` to see the local entropy of an XOR'd stream).
    *   **Breadth**: Using `--rgb` to drive R, G, and B color channels in parallel as a visual coincidence detector (e.g., *Where is the stream high-entropy, fast-changing, AND periodic?*).

#### **Slide 7: Closing the Loop: Bidirectional Inspect**
*   **Focus**: Reverse mapping from image pixels directly back to byte offsets and semantic meaning.
*   **Analytical Differentiator**: GUI-based reverse-engineering visualizers usually limit you to hover tooltips. `vizbin inspect` is completely **scriptable, mode-aware, and bidirectional**. Feed the exact coordinate (or byte offset) to get a multi-projection translation—such as the XOR operands or local entropy calculation—to seamlessly hand off to your hex editor or disassembler.

#### **Slide 8: Vizbin vs. The Field (The Operational Edge)**
*   **Focus**: Side-by-side comparison with heavy visualization tools like **Binocle** or **Cantor.dust**.
*   **Operational Differentiator**:
    *   *The Legacy Problem*: GUI visualization engines are bulky, require heavy graphical environments, and are difficult to deploy on the fly.
    *   *The Vizbin Advantage*: **Zero runtime dependencies**. It is written entirely in pure Python standard library—meaning the BMP writer and LZW animated GIF encoder are implemented entirely from scratch. You can drop the raw script onto an air-gapped forensics box over SSH with no internet, no `pip`, and no X11 required.

#### **Slide 9: Roadmap v0.5.0: Structure & Scale**
*   **Focus**: Introduce upcoming features that turn Vizbin into a proactive RE automated assistant.
    *   **Structure Inference (The Flagship)**: Closes the loop. Once `suggest` finds stride \\(N\\), Vizbin profiles each column of the record grid (byte-class, entropy, delta, monotonicity) to generate a draft layout (e.g., *"188-byte records: col 0 = monotonic counter, cols 12-31 = printable ASCII"*). It will export this structure directly as a Kaitai `.ksy` stub, Python `struct`, or 010 Editor template.
    *   **`profile --json`**: Translates Vizbin from a display tool to a machine-readable sensor. Emits file fingerprints (entropy histograms, byte distributions, strides) allowing users to run it programmatically over 100k files to cluster malware or flag firmware anomalies in a single terminal pipe.

#### **Slide 10: Roadmap v0.5.0: SSH, Diffing & Senses**
*   **Focus**: The lower-friction adoption hooks and analysis features.
    *   **Terminal Rendering (`--term`)**: Low-friction terminal-native view using 24-bit ANSI color and half-block characters. View binary visuals directly over SSH without any X11 forward or image file transfer.
    *   **Structural Diff (`diff`)**: Highlights structural transitions between two files (e.g., Firmware v1 vs v2, or patched malware variants) and aligns changes visually.
    *   **Auto-Segmentation (`segments`)**: Programmatic file carving that maps boundaries (e.g., where headers end, code starts, and compressed segments live) by combining entropy, magic bytes, and stride shifts.
    *   **Wildcard: Sonification**: Maps raw bytes/entropy directly into a pure-stdlib WAV audio file. Periodicity becomes immediately audible to the human ear.

#### **Slide 11: Setup & Commands Cheat Sheet**
*   **Focus**: Show how easy it is to spin up. Highlight that it requires Python 3.9+ with zero external setup. Provide a quick reference cheat sheet for the main commands (`render`, `suggest`, `contact`, `animate`, `inspect`, `bmp`/`unbmp`).
