"""Visual layer — matches the mockups approved in design review. Keep this
file the single place that knows about hex values and bubble markup; app.py
and pages/ should only call these helpers, never inline their own styles.

Design principle this encodes: candidate-facing screens must read as
ordinary workplace messaging, not an assessment product. No progress
counters, no visible scores. The debrief beat is the one deliberate
register shift (deep warm-brown gradient header) — see render_agent_header.

Visual direction: Warm Editorial — terracotta/amber gradients on a warm
cream base, applied consistently across the candidate app and the
reviewer dossier (pages/1_Reviewer_Dossier.py mirrors this palette; keep
the two in sync if you change colors here).
"""
import hashlib
import uuid


def escape_html(text) -> str:
    """HTML-escape then convert newlines to <br>. Use this for ANY text that
    flows from a user, a model, or free-form content into an HTML string
    passed to st.markdown(unsafe_allow_html=True) — candidate input, LLM
    output, anything not a hardcoded literal in this codebase. Order matters:
    & must be escaped before < and >, or the entities themselves get
    mangled."""
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )


def flatten_html(html: str) -> str:
    """Strip leading whitespace from every line before handing HTML to
    st.markdown(unsafe_allow_html=True). Streamlit runs markdown content
    through a Markdown parser first, and Markdown treats any line indented
    4+ spaces as a literal code block — which silently breaks nested,
    indented HTML built from readable multi-line f-strings. Call this on
    every multi-line HTML string before rendering it; single-line strings
    don't need it, but it's harmless if applied anyway."""
    return "\n".join(line.lstrip() for line in html.splitlines())


# --- Illustrated avatars ---------------------------------------------------
# Approved design: a simple line-art person (head circle + shoulder arc),
# role color moved to "clothing," varied skin tone and hairstyle on top.
# Deliberately NOT emoji, NOT photorealistic, NOT exaggerated caricature.
#
# The silhouette shape stays IDENTICAL across every agent — only color,
# skin tone, and hairstyle vary. This was a deliberate call, not an
# oversight: varying the shape/features per agent would mean making small
# implicit choices about what "the senior analyst" or "the underperformer"
# looks like, and that's a stereotype risk worth avoiding by construction
# rather than catching after the fact.
#
# Appearance is derived deterministically from agent_id (a stable hash, not
# random) so the same agent looks the same every time, but new agents
# (there are 7 across both sessions now, more likely later) get a
# reasonably varied look automatically — no hand-curating each new
# character's palette.
_AVATAR_PALETTE = [
    {"accent": "#D9622E", "bg": "#FBE4D6"},  # burnt orange
    {"accent": "#B8791F", "bg": "#F7E8CE"},  # amber
    {"accent": "#A8425A", "bg": "#F7DEE3"},  # berry rose
    {"accent": "#6B4226", "bg": "#EDE0D3"},  # deep terracotta-brown
    {"accent": "#8A7A2E", "bg": "#F0EBD3"},  # olive gold
    {"accent": "#A64B2A", "bg": "#F5DED2"},  # rust
    {"accent": "#7A4A6B", "bg": "#EFE0EC"},  # warm plum
]
_SKIN_TONES = ["#C68863", "#8D5524", "#F1C27D", "#E8B894", "#A9714A", "#6B4226"]
_HAIR_COLORS = ["#2B1B12", "#1C1C1C", "#3B2A1E", "#8A8A85", "#5C4033"]
_HAIRSTYLES = ["long", "short", "bun"]


def _agent_look(agent_id: str) -> dict:
    h = int(hashlib.md5(agent_id.encode()).hexdigest(), 16)
    palette = _AVATAR_PALETTE[h % len(_AVATAR_PALETTE)]
    return {
        "accent": palette["accent"],
        "bg": palette["bg"],
        "skin": _SKIN_TONES[(h // 7) % len(_SKIN_TONES)],
        "hair_color": _HAIR_COLORS[(h // 47) % len(_HAIR_COLORS)],
        "hairstyle": _HAIRSTYLES[(h // 211) % len(_HAIRSTYLES)],
    }


def _hair_svg(hairstyle: str, hair_color: str) -> str:
    if hairstyle == "long":
        return f'<ellipse cx="28" cy="26" rx="12" ry="16" fill="{hair_color}"/>'
    if hairstyle == "bun":
        return (
            f'<ellipse cx="28" cy="19" rx="10" ry="9" fill="{hair_color}"/>'
            f'<circle cx="34" cy="11" r="4.5" fill="{hair_color}"/>'
        )
    return f'<ellipse cx="28" cy="17" rx="10" ry="8" fill="{hair_color}"/>'  # short


def avatar_svg(agent_id: str, size: int = 32) -> str:
    """Inline SVG for one agent's avatar, sized to `size`px. Safe to call
    more than once for the same agent on one page (e.g. header + typing
    indicator both showing) — each call gets its own clipPath id so the
    SVGs don't collide in the DOM."""
    look = _agent_look(agent_id)
    hair = _hair_svg(look["hairstyle"], look["hair_color"])
    clip_id = f"avclip-{agent_id}-{uuid.uuid4().hex[:6]}"
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 56 56" style="display:block;">'
        f'<circle cx="28" cy="28" r="26" fill="{look["bg"]}"/>'
        f'<clipPath id="{clip_id}"><circle cx="28" cy="28" r="26"/></clipPath>'
        f'<g clip-path="url(#{clip_id})">'
        f'{hair}'
        f'<circle cx="28" cy="23" r="9" fill="{look["skin"]}"/>'
        f'<path d="M8,56 a20,20 0 0,1 40,0 Z" fill="{look["accent"]}"/>'
        f'</g></svg>'
    )


BASE_CSS = """
<style>
.stApp {
    background: linear-gradient(160deg, #FFF8F0 0%, #FCEEDC 100%);
}
.lsim-panel {
    background: #FFFDFA;
    border: 1px solid #F0DCC4;
    border-radius: 12px;
    overflow: hidden;
    margin-bottom: 1rem;
}
.lsim-panel.debrief { background: #FFFDFA; border-color: #E9D6C3; }
.lsim-header {
    padding: 14px 18px;
    background: #FBEAD6;
    border-bottom: 1px solid #F0DCC4;
    display: flex;
    align-items: center;
    gap: 10px;
}
.lsim-header.debrief-header {
    background: linear-gradient(120deg, #7A3E1D 0%, #6B3A1F 100%);
    border-bottom: none;
    display: block;
}
.lsim-avatar-wrap {
    width: 32px; height: 32px; border-radius: 50%; overflow: hidden;
    flex-shrink: 0; position: relative;
}
.lsim-status-dot {
    position: absolute; bottom: 0; right: 0; width: 8px; height: 8px;
    border-radius: 50%; background: #6FBF73; border: 2px solid #FBEAD6;
}
.lsim-name { font-size: 14px; font-weight: 600; color: #5C3A22; }
.lsim-role { font-size: 12px; color: #8A6A4E; }
.lsim-debrief-eyebrow { font-size: 12px; color: #E8CBAE; }
.lsim-debrief-title { font-size: 14px; font-weight: 600; color: #fff; margin-top: 2px; }
.lsim-thread { padding: 18px; display: flex; flex-direction: column; gap: 12px; }
.lsim-bubble { max-width: 78%; padding: 10px 14px; font-size: 14px; line-height: 1.5; }
.lsim-bubble.agent {
    align-self: flex-start; background: #F3E3D0; color: #4A3320;
    border-radius: 14px 14px 14px 4px;
}
.lsim-bubble.agent.debrief {
    background: #fff; border: 1px solid #EBD9C4; color: #4A3320;
}
.lsim-bubble.candidate {
    align-self: flex-end; color: #fff;
    background: linear-gradient(135deg, #E8935A 0%, #D9622E 100%);
    border-radius: 14px 14px 4px 14px;
}
.lsim-typing-row {
    padding: 8px 18px 14px; display: flex; align-items: center; gap: 10px;
}
.lsim-typing-text { font-size: 13px; color: #8A6A4E; font-style: italic; }
.lsim-sound-bars { display: flex; align-items: flex-end; gap: 2px; height: 14px; }
.lsim-sound-bars span {
    width: 3px; border-radius: 2px; display: inline-block;
    animation: lsimBar 0.9s ease-in-out infinite;
}
.lsim-sound-bars span:nth-child(1) { height: 6px; animation-delay: 0s; }
.lsim-sound-bars span:nth-child(2) { height: 12px; animation-delay: 0.15s; }
.lsim-sound-bars span:nth-child(3) { height: 8px; animation-delay: 0.3s; }
@keyframes lsimBar {
    0%, 100% { transform: scaleY(0.5); }
    50% { transform: scaleY(1); }
}
@media (prefers-reduced-motion: reduce) {
    .lsim-sound-bars span { animation: none; }
}
.lsim-transition {
    background: #F5E6D3; border-radius: 12px; padding: 40px 24px;
    text-align: center; margin-bottom: 1rem;
}
.lsim-transition-text { font-size: 14px; color: #8A6A4E; font-style: italic; }
.lsim-dots { margin-top: 16px; display: flex; justify-content: center; gap: 6px; }
.lsim-dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.lsim-dot.active { background: #D9622E; }
.lsim-dot.inactive { background: #E9D6C3; }
.lsim-briefing { font-size: 17px; color: #5C3A22; line-height: 1.5; margin: 0 0 16px 2px; }

/* One restrained entrance moment for the start of a beat — never replays on
   every rerun (see app.py's revealed_beats guard). Deliberately just an
   opacity + gentle rise, nothing bouncy — a passage-of-time cue, not a
   reward moment. Keep it this quiet; see ui_style.py module docstring. */
@keyframes lsimFadeIn {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
.lsim-fade-in { animation: lsimFadeIn 0.7s ease-out; }

@media (prefers-reduced-motion: reduce) {
    .lsim-fade-in { animation: none; }
}

/* Mobile reflow — the base styles above assume the ~640-680px desktop
   width Streamlit's centered layout gives by default. Below ~480px,
   tighten padding and widen bubbles so text isn't cramped into a sliver. */
@media (max-width: 480px) {
    .lsim-header { padding: 12px 14px; gap: 8px; }
    .lsim-thread { padding: 14px; gap: 10px; }
    .lsim-bubble { max-width: 88%; font-size: 13.5px; padding: 9px 12px; }
    .lsim-avatar-wrap { width: 28px; height: 28px; }
    .lsim-briefing { font-size: 15px; margin: 0 0 12px 2px; }
    .lsim-transition { padding: 28px 16px; }
}

.lsim-error-notice {
    background: #FBDCE3; color: #7A2436; border-radius: 8px;
    padding: 12px 16px; font-size: 13.5px; margin: 0.5rem 0;
}
</style>
"""


def inject_css(st) -> None:
    st.markdown(flatten_html(BASE_CSS), unsafe_allow_html=True)


def render_agent_header(st, agent_id: str, name: str, role: str, debrief: bool = False) -> None:
    if debrief:
        html = f"""
        <div class="lsim-header debrief-header">
            <div class="lsim-debrief-eyebrow">End-of-week check-in</div>
            <div class="lsim-debrief-title">With {escape_html(name)}</div>
        </div>
        """
    else:
        avatar = avatar_svg(agent_id, size=32)
        html = f"""
        <div class="lsim-header">
            <div class="lsim-avatar-wrap">{avatar}<span class="lsim-status-dot"></span></div>
            <div>
                <div class="lsim-name">{escape_html(name)}</div>
                <div class="lsim-role">{escape_html(role)}</div>
            </div>
        </div>
        """
    st.markdown(flatten_html(html), unsafe_allow_html=True)


def render_typing_indicator(st, agent_id: str, name: str) -> None:
    """Shown while waiting on a model reply, replacing the blank spinner.
    The avatar here deliberately has no status dot — that's reserved for
    the header, keeps this visually distinct as a transient state."""
    avatar = avatar_svg(agent_id, size=32)
    html = f"""
    <div class="lsim-typing-row">
        <div class="lsim-avatar-wrap">{avatar}</div>
        <div class="lsim-sound-bars" style="color:{_agent_look(agent_id)['accent']};">
            <span></span><span></span><span></span>
        </div>
        <div class="lsim-typing-text">{escape_html(name)} is typing…</div>
    </div>
    """
    st.markdown(flatten_html(html), unsafe_allow_html=True)


def render_thread(st, transcript: list[dict], debrief: bool = False) -> None:
    bubbles = ""
    for turn in transcript:
        is_candidate = turn["speaker"] == "Candidate"
        cls = "candidate" if is_candidate else ("agent debrief" if debrief else "agent")
        # Escape HTML, then turn any embedded newline into <br> — chat_input
        # is single-line by keyboard but a candidate can still paste
        # multi-line text, and a model reply could in principle break its
        # brevity instruction. Both would otherwise either vanish (no line
        # break rendering) or, worse, reintroduce the code-block bug if a
        # pasted line happened to start with 4+ spaces.
        text = escape_html(turn["text"])
        bubbles += f'<div class="lsim-bubble {cls}">{text}</div>'
    st.markdown(flatten_html(f'<div class="lsim-thread">{bubbles}</div>'), unsafe_allow_html=True)


def render_transition(st, text: str) -> None:
    html = f"""
    <div class="lsim-transition lsim-fade-in">
        <div class="lsim-transition-text">{text}</div>
        <div class="lsim-dots">
            <span class="lsim-dot active"></span>
            <span class="lsim-dot inactive"></span>
            <span class="lsim-dot inactive"></span>
        </div>
    </div>
    """
    st.markdown(flatten_html(html), unsafe_allow_html=True)


def render_briefing(st, text: str, animate: bool = False) -> None:
    """The scenario briefing shown once a beat's chat screen opens.
    `animate` should be True only the first time this beat is rendered —
    see app.py's revealed_beats guard. Without that guard this would
    replay on every message send, which reads as distracting, not restrained."""
    cls = "lsim-briefing lsim-fade-in" if animate else "lsim-briefing"
    safe_text = escape_html(text)
    st.markdown(flatten_html(f'<div class="{cls}">{safe_text}</div>'), unsafe_allow_html=True)


def render_error_notice(st, text: str) -> None:
    """Shown when an agent's model call fails — a plain, calm notice, not a
    stack trace. Deliberately doesn't try to stay in character (a garbled
    in-character excuse would be worse than an honest system notice here)."""
    safe_text = escape_html(text)
    st.markdown(flatten_html(f'<div class="lsim-error-notice">{safe_text}</div>'), unsafe_allow_html=True)
