"""Generate AGON Demonstration PDF and Full-Stack Source Code PDF."""

from __future__ import annotations

import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)
LOGO_DARK = ROOT / "static" / "images" / "agon-logo-dark.jpg"
SCRATCH_DIR = Path(
    r"C:\Users\Dell\.gemini\antigravity\brain\cc717ebc-91b8-455f-8aff-ac563b3e9b3b\scratch"
)

SOURCE_FILES: list[tuple[str, str]] = [
    ("app.py", "Flask Web Server, REST API Endpoints & Pipeline Orchestrator"),
    ("detectors/__init__.py", "Detectors Package Marker"),
    ("detectors/metadata_analyzer.py", "EXIF, PNG Chunks, XMP/C2PA & Video Container Provenance Analyzer"),
    ("detectors/image_forensics.py", "2D FFT Spectrum, ELA, Sensor Noise Residual, Color & Score Fusion"),
    ("detectors/video_forensics.py", "OpenCV Keyframe Extraction & Temporal Shimmer Analyzer"),
    ("detectors/external_models.py", "Optional Local ONNX & Hugging Face Inference API Integration"),
    ("detectors/sample_generator.py", "Built-in Synthetic AI & Camera Demo Media Generator"),
    ("templates/index.html", "Main Web UI HTML Template"),
    ("static/css/style.css", "Dark-Mode Forensic Lab Stylesheet & Responsive Layout"),
    ("static/js/app.js", "Frontend Upload, SVG Gauge, Heatmap Switcher, Timeline & Export Logic"),
    ("tests/test_app.py", "Automated Pytest Suite (6 End-to-End Tests)"),
    ("requirements.txt", "Python Package Dependencies"),
]


def _add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(0.6 * inch, 0.38 * inch, "AGON — Detect • Verify • Stay Informed | github.com/Rohith2005-rakshu/AGON")
    canvas.drawRightString(A4[0] - 0.6 * inch, 0.38 * inch, f"Page {doc.page}")
    canvas.restoreState()


def build_demonstration_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.65 * inch,
        title="AGON — Live Demonstration Guide",
        author="Rohith2005-rakshu",
    )
    styles = getSampleStyleSheet()
    title_st = ParagraphStyle("T", parent=styles["Title"], fontSize=21, textColor=colors.HexColor("#0f172a"), spaceAfter=4)
    sub_st = ParagraphStyle("S", parent=styles["Normal"], fontSize=10.5, textColor=colors.HexColor("#0284c7"), alignment=TA_CENTER, spaceAfter=12)
    h1_st = ParagraphStyle("H1", parent=styles["Heading1"], fontSize=13.5, textColor=colors.HexColor("#0f172a"), spaceBefore=10, spaceAfter=5)
    h2_st = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=11, textColor=colors.HexColor("#0369a1"), spaceBefore=8, spaceAfter=4)
    body_st = ParagraphStyle("B", parent=styles["Normal"], fontSize=9.3, leading=13, textColor=colors.HexColor("#1e293b"), spaceAfter=5)
    cell_st = ParagraphStyle("C", parent=styles["Normal"], fontSize=8.2, leading=10.5, textColor=colors.HexColor("#1e293b"))
    head_st = ParagraphStyle("CH", parent=styles["Normal"], fontSize=8.4, leading=10.5, textColor=colors.white)
    code_st = ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=8.0,
        leading=10.5,
        textColor=colors.HexColor("#e2e8f0"),
        backColor=colors.HexColor("#0f172a"),
        leftIndent=6,
        rightIndent=6,
        spaceBefore=4,
        spaceAfter=6,
    )

    def _code_box(text: str):
        t = Table([[Preformatted(text, code_st)]], colWidths=[7.25 * inch])
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#0f172a")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#334155")),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]))
        return t

    story = []
    if LOGO_DARK.exists():
        story.append(RLImage(str(LOGO_DARK), width=4.0 * inch, height=1.19 * inch))
        story.append(Spacer(1, 6))

    story.append(Paragraph("AGON — Live Demonstration Guide", title_st))
    story.append(Paragraph("Step-by-Step Walkthrough, Visual Forensic Comparison & API Demo", sub_st))

    story.append(Paragraph("1. Launching the Website Locally", h1_st))
    story.append(Paragraph(
        "Run the following commands from the project root directory to install dependencies and launch the Flask server:",
        body_st,
    ))
    story.append(_code_box(
        "pip install -r requirements.txt\npython app.py\n# Open http://127.0.0.1:5000 in your browser"
    ))

    story.append(Paragraph("2. Interactive Browser Demonstration (Step-by-Step)", h1_st))
    steps = [
        ("Step 1 — Landing & Threshold Guide:", "Verify the AGON header, upload dropzone, and the 'How AGON Considers Media AI-Generated' scale (4–41% Likely Authentic, 42–67% Uncertain, 68–98% Likely AI-Generated)."),
        ("Step 2 — Run Built-in AI Diffusion Sample:", "Click 'AI Diffusion Sample (PNG)'. AGON analyzes PNG chunks + pixel noise/FFT and displays 92.0% — Likely AI-Generated."),
        ("Step 3 — Inspect Visual Forensic Lab:", "Toggle between '2x2 Grid', 'Original', '2D FFT', 'ELA', and 'Noise'. Notice bright off-center periodic grid dots in the 2D FFT spectrum and dark uniform patches in the Noise Residual map."),
        ("Step 4 — Run Built-in Camera Photo Sample:", "Click 'Camera Photo Sample (JPG)'. AGON extracts 7 Canon EOS R6 EXIF tags + organic 1/f noise grain and reports 20.4% — Likely Authentic Media."),
        ("Step 5 — Run Built-in Video Sample:", "Click 'AI Video Sample (MP4)'. AGON decodes 10 keyframes across 24 frames (2.0s @ 12 fps), displays the playable video, plots the Canvas Temporal Timeline chart, and lets you click frame thumbnails to seek."),
        ("Step 6 — Custom Upload, Boost & Export:", "Drag and drop any personal image or video. Optionally open 'AI Model Boost' to supply a Hugging Face API token, then click 'Export JSON Report' to download agon_report_&lt;filename&gt;.json."),
    ]
    for title_txt, desc_txt in steps:
        story.append(Paragraph(f"<b>{title_txt}</b> {desc_txt}", body_st))

    story.append(Paragraph("3. Observed Live Demo Results Summary", h1_st))
    demo_rows = [
        [
            Paragraph("<b>Demo Input</b>", head_st),
            Paragraph("<b>Type</b>", head_st),
            Paragraph("<b>AI %</b>", head_st),
            Paragraph("<b>Verdict</b>", head_st),
            Paragraph("<b>Observed Signal Breakdown</b>", head_st),
        ],
        [
            Paragraph("demo_ai_diffusion_sample.png", cell_st),
            Paragraph("Image", cell_st),
            Paragraph("<b>92.0%</b>", cell_st),
            Paragraph("Likely AI-Generated", cell_st),
            Paragraph("Noise smoothness 75.6%, ELA 50.7%, Stable Diffusion PNG metadata 96.0% (1457 ms)", cell_st),
        ],
        [
            Paragraph("demo_camera_photo_sample.jpg", cell_st),
            Paragraph("Image", cell_st),
            Paragraph("<b>20.4%</b>", cell_st),
            Paragraph("Likely Authentic Media", cell_st),
            Paragraph("Noise 10.0% (natural sensor grain), FFT 28.2%, Canon EOS R6 7 EXIF tags 14.0% (1085 ms)", cell_st),
        ],
        [
            Paragraph("demo_ai_video_sample.mp4", cell_st),
            Paragraph("Video", cell_st),
            Paragraph("<b>23.4%</b>", cell_st),
            Paragraph("Likely Authentic Media", cell_st),
            Paragraph("10 keyframes, temporal score 29.3%, Lavf63.1.102 muxer metadata, peak-frame maps", cell_st),
        ],
    ]
    dt = Table(demo_rows, colWidths=[1.65 * inch, 0.55 * inch, 0.6 * inch, 1.3 * inch, 3.15 * inch])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#fff1f2"), colors.HexColor("#ecfdf5"), colors.HexColor("#f8fafc")]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(dt)

    # Page 2: Visual Side-by-Side Comparison
    story.append(PageBreak())
    story.append(Paragraph("4. Visual Forensic Lab Comparison (AI Sample vs. Camera Sample)", h1_st))

    ai_vis = [
        ("Original (AI Sample)", SCRATCH_DIR / "demo_original.png"),
        ("2D FFT (Periodic Dots)", SCRATCH_DIR / "demo_fft_spectrum.png"),
        ("ELA Heatmap", SCRATCH_DIR / "demo_ela_heatmap.png"),
        ("Noise (Dark/Smooth)", SCRATCH_DIR / "demo_noise_residual.png"),
    ]
    if all(p.exists() for _, p in ai_vis):
        story.append(Paragraph("A. AI Diffusion Sample (demo_ai_diffusion_sample.png — 92.0% AI)", h2_st))
        t_ai = Table(
            [
                [RLImage(str(p), width=1.55 * inch, height=1.55 * inch) for _, p in ai_vis],
                [Paragraph(f"<b>{lbl}</b>", ParagraphStyle("CA", parent=cell_st, alignment=TA_CENTER)) for lbl, _ in ai_vis],
            ],
            colWidths=[1.8 * inch] * 4,
        )
        t_ai.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_ai)
        story.append(Spacer(1, 8))

    cam_vis = [
        ("Original (Camera Sample)", SCRATCH_DIR / "cam_original.png"),
        ("2D FFT (Natural 1/f)", SCRATCH_DIR / "cam_fft_spectrum.png"),
        ("ELA Heatmap", SCRATCH_DIR / "cam_ela_heatmap.png"),
        ("Noise (Organic Grain)", SCRATCH_DIR / "cam_noise_residual.png"),
    ]
    if all(p.exists() for _, p in cam_vis):
        story.append(Paragraph("B. Camera Photo Sample (demo_camera_photo_sample.jpg — 20.4% AI)", h2_st))
        t_cam = Table(
            [
                [RLImage(str(p), width=1.55 * inch, height=1.55 * inch) for _, p in cam_vis],
                [Paragraph(f"<b>{lbl}</b>", ParagraphStyle("CC", parent=cell_st, alignment=TA_CENTER)) for lbl, _ in cam_vis],
            ],
            colWidths=[1.8 * inch] * 4,
        )
        t_cam.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_cam)

    story.append(Paragraph("5. Command-Line & REST API Demonstration", h1_st))
    story.append(_code_box(
        "# 1. Check server health & supported formats\n"
        "curl http://127.0.0.1:5000/api/health\n\n"
        "# 2. Analyze any local image or video via POST /api/analyze\n"
        "curl -X POST -F \"file=@sample_photo.jpg\" http://127.0.0.1:5000/api/analyze\n\n"
        "# 3. Run automated verification test suite\n"
        "python -m pytest -v   # Observed: 6 passed"
    ))

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)


def _wrap_source_with_line_numbers(content: str, max_width: int = 92) -> str:
    lines_out: list[str] = []
    for idx, raw_line in enumerate(content.splitlines(), start=1):
        prefix = f"{idx:03d} | "
        cont_prefix = "    | "
        expanded = raw_line.replace("\t", "    ")
        if len(expanded) <= max_width:
            lines_out.append(prefix + expanded)
        else:
            wrapped = textwrap.wrap(
                expanded,
                width=max_width,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
            for w_i, chunk in enumerate(wrapped):
                lines_out.append((prefix if w_i == 0 else cont_prefix) + chunk)
    return "\n".join(lines_out)


def build_fullstack_code_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        leftMargin=0.5 * inch,
        rightMargin=0.5 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.6 * inch,
        title="AGON — Complete Full-Stack Source Code",
        author="Rohith2005-rakshu",
    )
    styles = getSampleStyleSheet()
    title_st = ParagraphStyle("CT", parent=styles["Title"], fontSize=21, textColor=colors.HexColor("#0f172a"), spaceAfter=4)
    sub_st = ParagraphStyle("CS", parent=styles["Normal"], fontSize=10.5, textColor=colors.HexColor("#0284c7"), alignment=TA_CENTER, spaceAfter=14)
    h1_st = ParagraphStyle("CH1", parent=styles["Heading1"], fontSize=13, textColor=colors.HexColor("#0f172a"), spaceBefore=8, spaceAfter=6)
    file_hdr_st = ParagraphStyle(
        "FH",
        parent=styles["Heading2"],
        fontSize=10.5,
        leading=14,
        textColor=colors.white,
        backColor=colors.HexColor("#0f172a"),
        borderPadding=(5, 7, 5, 7),
        spaceBefore=6,
        spaceAfter=4,
    )
    file_desc_st = ParagraphStyle("FD", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#475569"), spaceAfter=4)
    code_st = ParagraphStyle(
        "SrcCode",
        fontName="Courier",
        fontSize=6.8,
        leading=8.8,
        textColor=colors.HexColor("#0f172a"),
        backColor=colors.HexColor("#f8fafc"),
        leftIndent=2,
        rightIndent=2,
        spaceAfter=8,
    )
    cell_st = ParagraphStyle("TC", parent=styles["Normal"], fontSize=8.2, leading=10.5, textColor=colors.HexColor("#1e293b"))
    head_st = ParagraphStyle("TH", parent=styles["Normal"], fontSize=8.4, leading=10.5, textColor=colors.white)

    story = []
    if LOGO_DARK.exists():
        story.append(RLImage(str(LOGO_DARK), width=3.8 * inch, height=1.13 * inch))
        story.append(Spacer(1, 6))

    story.append(Paragraph("AGON — Complete Full-Stack Source Code", title_st))
    story.append(Paragraph("Backend (Flask + Forensics + OpenCV + ONNX)  |  Frontend (HTML5 + CSS3 + JS)  |  Tests", sub_st))

    story.append(Paragraph("Project File Index", h1_st))
    idx_rows = [[
        Paragraph("<b>#</b>", head_st),
        Paragraph("<b>File Path</b>", head_st),
        Paragraph("<b>Role in Stack</b>", head_st),
        Paragraph("<b>Lines</b>", head_st),
    ]]
    loaded_files: list[tuple[str, str, str, int]] = []
    for i, (rel_path, role) in enumerate(SOURCE_FILES, start=1):
        full_p = ROOT / rel_path
        text = full_p.read_text(encoding="utf-8")
        line_cnt = len(text.splitlines())
        loaded_files.append((rel_path, role, text, line_cnt))
        idx_rows.append([
            Paragraph(str(i), cell_st),
            Paragraph(f"<b>{rel_path}</b>", cell_st),
            Paragraph(role, cell_st),
            Paragraph(str(line_cnt), cell_st),
        ])

    idx_table = Table(idx_rows, colWidths=[0.35 * inch, 2.05 * inch, 4.25 * inch, 0.55 * inch])
    idx_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(idx_table)

    for rel_path, role, text, line_cnt in loaded_files:
        story.append(PageBreak())
        story.append(Paragraph(f"FILE: {rel_path}  ({line_cnt} lines)", file_hdr_st))
        story.append(Paragraph(f"<i>Purpose: {role}</i>", file_desc_st))

        numbered = _wrap_source_with_line_numbers(text, max_width=94)
        # Split into chunks of ~68 lines so ReportLab flows cleanly across pages without huge block overflow
        chunk_lines = numbered.splitlines()
        chunk_size = 68
        for start in range(0, len(chunk_lines), chunk_size):
            block = "\n".join(chunk_lines[start : start + chunk_size])
            story.append(Preformatted(block, code_st))

    doc.build(story, onFirstPage=_add_page_number, onLaterPages=_add_page_number)


if __name__ == "__main__":
    demo_pdf = DOCS_DIR / "AGON_Demonstration.pdf"
    code_pdf = DOCS_DIR / "AGON_FullStack_Code.pdf"
    build_demonstration_pdf(demo_pdf)
    build_fullstack_code_pdf(code_pdf)
    print("Generated:", demo_pdf, demo_pdf.stat().st_size, "bytes")
    print("Generated:", code_pdf, code_pdf.stat().st_size, "bytes")
