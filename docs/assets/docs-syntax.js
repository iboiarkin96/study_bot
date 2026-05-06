/**
 * docs-syntax.js — Lightweight, zero-dependency syntax highlighter.
 *
 * Design principles:
 *   - Self-contained: no CDN, no build step, no runtime dependencies.
 *   - Safe: escapes HTML first, then tokenizes; never touches already-highlighted text.
 *   - Theming: emits `st-*` span classes; colors are CSS custom properties that
 *     automatically track the light/dark theme (see docs-syntax-theme.css).
 *   - Opt-in: only runs on <pre><code> blocks; inline <code> is unchanged.
 *   - Graceful: silently skips blocks it can't parse; never throws to the page.
 *   - Accessible: does not change semantics; screen readers see plain text.
 *
 * Supported languages (auto-detected or via class="language-*"):
 *   python · bash / sh / shell · json · yaml / yml · http · javascript / js
 *
 * Token CSS classes (see docs-syntax-theme.css for color values):
 *   st-kw   keyword          st-str  string
 *   st-cmt  comment          st-num  number
 *   st-key  object key       st-bi   builtin / type
 *   st-var  variable ($VAR)  st-flag CLI flag (--flag)
 *   st-dec  decorator        st-op   operator / punctuation
 */

(function initDocsSyntaxHighlight() {
  "use strict";

  /* ── Bootstrap ─────────────────────────────────────────────────────────── */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", highlightAll);
  } else {
    // In case the script loads deferred after DOMContentLoaded
    if (typeof requestIdleCallback === "function") {
      requestIdleCallback(highlightAll, { timeout: 800 });
    } else {
      setTimeout(highlightAll, 0);
    }
  }

  /* ── Entry point ────────────────────────────────────────────────────────── */

  function highlightAll() {
    const blocks = document.querySelectorAll("pre > code");
    for (const block of blocks) {
      try {
        const raw = block.textContent || "";
        const dedented = dedent(raw);
        const reformatted = reformatJSONBody(dedented);
        const lang = detectLanguage(block);
        const changed = reformatted !== raw;
        if (!lang && !changed) { continue; }
        const escaped = escapeHTML(reformatted);
        block.innerHTML = lang ? tokenize(escaped, lang) : escaped;
        if (lang) {
          const pre = block.closest("pre");
          if (pre) { pre.setAttribute("data-lang", lang); }
        }
      } catch (_) {
        // Fail silently — never break the page for a cosmetic feature.
      }
    }
  }

  /* ── Dedent ─────────────────────────────────────────────────────────────────
   * Strip the common leading whitespace shared by every non-blank line, and
   * trim leading/trailing blank lines. Lets <pre><code> blocks stay readable
   * even when the HTML source is deeply indented (e.g. nested in <section>s).
   *
   * Special case: when the opening <code> tag and the first content line are
   * on the same source line (e.g. `<pre><code>PATCH …`), the first line has
   * zero indent while the body lines carry the surrounding HTML indent. In
   * that case we compute the body's common indent separately and leave the
   * first line alone — otherwise the first line's zero indent would force
   * the common min to zero and the dedent would no-op.
   */
  function dedent(text) {
    if (!text) { return text; }
    const lines = text.replace(/\r\n?/g, "\n").split("\n");
    while (lines.length && !lines[0].trim()) { lines.shift(); }
    while (lines.length && !lines[lines.length - 1].trim()) { lines.pop(); }
    if (!lines.length) { return ""; }

    const leadLen = (line) => {
      const m = /^[ \t]*/.exec(line);
      return m ? m[0].length : 0;
    };

    const firstIndent = leadLen(lines[0]);
    let bodyMin = Infinity;
    for (let i = 1; i < lines.length; i += 1) {
      if (!lines[i].trim()) { continue; }
      const len = leadLen(lines[i]);
      if (len < bodyMin) { bodyMin = len; }
    }

    // Single non-blank line case: dedent by its own leading whitespace.
    if (!isFinite(bodyMin)) {
      if (firstIndent === 0) { return lines.join("\n"); }
      return lines.map((l) => l.slice(Math.min(firstIndent, leadLen(l)))).join("\n");
    }

    // First line was inlined with <code> (zero indent) while the body
    // carries the HTML source indent: dedent body only, keep first line.
    if (firstIndent < bodyMin) {
      const out = [lines[0]];
      for (let i = 1; i < lines.length; i += 1) {
        out.push(lines[i].slice(Math.min(bodyMin, leadLen(lines[i]))));
      }
      return out.join("\n");
    }

    // Normal case: every line shares a common indent.
    const min = Math.min(firstIndent, bodyMin);
    if (min === 0) { return lines.join("\n"); }
    return lines.map((l) => l.slice(Math.min(min, leadLen(l)))).join("\n");
  }

  /* ── JSON body reindent ─────────────────────────────────────────────────────
   * After dedent, code blocks may contain a JSON object/array body with no
   * internal indentation (every key flush left inside the braces). Walk the
   * body lines tracking unescaped {[]} depth and re-emit each line with
   * 2-space indent matching its depth. Leaves head lines (HTTP request line,
   * status line, headers) untouched.
   *
   * The body is anything from the first line whose trimmed form starts with
   * `{` or `[` and is either at index 0 or preceded by a blank line. If no
   * such body is found, the text is returned unchanged — which keeps Python,
   * YAML, bash, etc. out of scope.
   */
  function reformatJSONBody(text) {
    if (!text) { return text; }
    const lines = text.split("\n");

    let bodyStart = -1;
    for (let i = 0; i < lines.length; i += 1) {
      if (!/^\s*[\{\[]/.test(lines[i])) { continue; }
      if (i === 0 || /^\s*$/.test(lines[i - 1])) {
        bodyStart = i;
        break;
      }
    }
    if (bodyStart === -1) { return text; }

    const out = lines.slice(0, bodyStart);
    let depth = 0;
    for (let i = bodyStart; i < lines.length; i += 1) {
      const stripped = lines[i].replace(/^[ \t]+/, "");
      if (!stripped) { out.push(""); continue; }

      let leadCloses = 0;
      while (
        leadCloses < stripped.length &&
        (stripped[leadCloses] === "}" || stripped[leadCloses] === "]")
      ) {
        leadCloses += 1;
      }
      const printDepth = Math.max(0, depth - leadCloses);
      out.push("  ".repeat(printDepth) + stripped);

      let inStr = false;
      let escape = false;
      let opens = 0;
      let closes = 0;
      for (let j = 0; j < stripped.length; j += 1) {
        const ch = stripped[j];
        if (escape) { escape = false; continue; }
        if (ch === "\\") { escape = true; continue; }
        if (ch === "\"") { inStr = !inStr; continue; }
        if (inStr) { continue; }
        if (ch === "{" || ch === "[") { opens += 1; }
        else if (ch === "}" || ch === "]") { closes += 1; }
      }
      depth += opens - closes;
      if (depth < 0) { depth = 0; }
    }
    return out.join("\n");
  }

  /* ── Language detection ─────────────────────────────────────────────────── */

  function detectLanguage(codeEl) {
    // Prefer explicit class="language-*" or "lang-*"
    for (const cls of codeEl.classList) {
      if (cls.startsWith("language-")) { return cls.slice(9).toLowerCase(); }
      if (cls.startsWith("lang-")) { return cls.slice(5).toLowerCase(); }
    }
    // Also check <pre> for the same class convention
    const pre = codeEl.closest("pre");
    if (pre) {
      for (const cls of pre.classList) {
        if (cls.startsWith("language-")) { return cls.slice(9).toLowerCase(); }
        if (cls.startsWith("lang-")) { return cls.slice(5).toLowerCase(); }
      }
    }
    // Content-based auto-detection (conservative — only very clear signals)
    const text = (codeEl.textContent || "").trimStart();
    if (/^[\s\S]*\bdef \w+\s*\(/.test(text)) { return "python"; }
    if (/^from \w+ import|^import \w+/.test(text)) { return "python"; }
    if (/^\s*\{[\s\S]*?\}[\s\n]*$/.test(text) && text.includes('"') && text.includes(":")) { return "json"; }
    if (/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+\//.test(text)) { return "http"; }
    if (/^HTTP\/\d/.test(text)) { return "http"; }
    if (/^\$\s/.test(text) || /\bmake\s+\w|^make\s+\w/m.test(text)) { return "bash"; }
    if (/^#!\/.*sh/.test(text)) { return "bash"; }
    return null;
  }

  /* ── HTML escaping ──────────────────────────────────────────────────────── */

  function escapeHTML(str) {
    return str
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  /* ── Span wrapper ───────────────────────────────────────────────────────── */

  function span(cls, text) {
    return `<span class="st-${cls}">${text}</span>`;
  }

  /* ── Dispatch ───────────────────────────────────────────────────────────── */

  const TOKENIZERS = {
    python:     tokenizePython,
    py:         tokenizePython,
    bash:       tokenizeBash,
    sh:         tokenizeBash,
    shell:      tokenizeBash,
    zsh:        tokenizeBash,
    json:       tokenizeJSON,
    yaml:       tokenizeYAML,
    yml:        tokenizeYAML,
    http:       tokenizeHTTP,
    javascript: tokenizeJS,
    js:         tokenizeJS,
    typescript: tokenizeJS,
    ts:         tokenizeJS,
  };

  function tokenize(escaped, lang) {
    const fn = TOKENIZERS[lang];
    return fn ? fn(escaped) : escaped;
  }

  /* ─────────────────────────────────────────────────────────────────────────
   * Tokenizers
   * Each function receives HTML-escaped source and returns HTML with
   * <span class="st-*"> wrappers. They MUST NOT double-escape — they operate
   * on the already-escaped string.
   * ───────────────────────────────────────────────────────────────────────── */

  /**
   * Python tokenizer.
   * Order: strings & comments first (to protect their content), then keywords, etc.
   */
  function tokenizePython(code) {
    // Capture groups: string literals (triple-quoted first), comments
    const STRINGS = /("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
    const COMMENTS = /(#[^\n]*)/g;
    const DECORATORS = /(@\w+)/g;
    const KEYWORDS = /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|pass|break|continue|and|or|not|in|is|None|True|False|lambda|yield|raise|del|global|nonlocal|async|await|match|case)\b/g;
    const BUILTINS = /\b(print|len|range|str|int|float|list|dict|set|tuple|bool|type|isinstance|issubclass|super|self|cls|staticmethod|classmethod|property|object|Exception|ValueError|TypeError|KeyError|IndexError|AttributeError)\b/g;
    const NUMBERS = /\b(\d+\.?\d*(?:[eE][+-]?\d+)?j?)\b/g;

    // We need to avoid tokenizing inside already-emitted spans. Strategy:
    // replace in-order with placeholder tokens to preserve ordering.
    const parts = [];
    let cursor = 0;
    let match;

    // Build a combined regex that alternates between strings and comments
    // to tokenize them first (protecting their content).
    const PROTECTED = new RegExp(
      [STRINGS.source, COMMENTS.source].join("|"),
      "g"
    );

    let out = "";
    cursor = 0;
    PROTECTED.lastIndex = 0;
    while ((match = PROTECTED.exec(code)) !== null) {
      // Emit unmatched text first (will be further tokenized)
      if (match.index > cursor) {
        out += tokenizePythonCode(
          code.slice(cursor, match.index),
          DECORATORS, KEYWORDS, BUILTINS, NUMBERS
        );
      }
      // Wrap matched string/comment
      if (match[0].startsWith("#")) {
        out += span("cmt", match[0]);
      } else {
        out += span("str", match[0]);
      }
      cursor = match.index + match[0].length;
    }
    // Remaining code after last match
    if (cursor < code.length) {
      out += tokenizePythonCode(code.slice(cursor), DECORATORS, KEYWORDS, BUILTINS, NUMBERS);
    }
    return out;
  }

  function tokenizePythonCode(code, DECORATORS, KEYWORDS, BUILTINS, NUMBERS) {
    return code
      .replace(DECORATORS, (m) => span("dec", m))
      .replace(KEYWORDS, (m) => span("kw", m))
      .replace(BUILTINS, (m) => span("bi", m))
      .replace(NUMBERS, (m) => span("num", m));
  }

  /**
   * Bash / shell tokenizer.
   */
  function tokenizeBash(code) {
    const STRINGS = /("(?:[^"\\]|\\.)*"|'[^']*')/g;
    const COMMENTS = /(#[^\n]*)/g;
    const VARS = /(\$\{?[A-Za-z_][A-Za-z_0-9]*\}?)/g;
    const COMMANDS = /\b(make|pip|pip3|python|python3|git|echo|export|source|cd|ls|cat|grep|curl|wget|docker|npm|yarn|chmod|mkdir|rm|cp|mv|touch|find|sort|head|tail|awk|sed|env|set|unset)\b/g;
    const FLAGS = /(?<=\s)(-{1,2}[\w-]+)/g;
    const SHEBANG = /^(#![^\n]*)/;

    let out = "";
    let cursor = 0;

    // Shebang line (must be line 1)
    const shebangMatch = code.match(SHEBANG);
    if (shebangMatch) {
      out += span("cmt", shebangMatch[0]);
      cursor = shebangMatch[0].length;
      code = code.slice(cursor);
      cursor = 0;
    }

    const PROTECTED = new RegExp([STRINGS.source, COMMENTS.source].join("|"), "g");
    PROTECTED.lastIndex = 0;
    let match;
    while ((match = PROTECTED.exec(code)) !== null) {
      if (match.index > cursor) {
        out += tokenizeBashCode(code.slice(cursor, match.index), VARS, COMMANDS, FLAGS);
      }
      if (match[0].startsWith("#")) {
        out += span("cmt", match[0]);
      } else {
        out += span("str", match[0]);
      }
      cursor = match.index + match[0].length;
    }
    if (cursor < code.length) {
      out += tokenizeBashCode(code.slice(cursor), VARS, COMMANDS, FLAGS);
    }
    return out;
  }

  function tokenizeBashCode(code, VARS, COMMANDS, FLAGS) {
    // Lookbehind for FLAGS won't work in all browsers (Safari<16.4), use split approach
    return code
      .replace(VARS, (m) => span("var", m))
      .replace(COMMANDS, (m) => span("kw", m))
      .replace(/(?:^|\s)(-{1,2}[\w-]+)/gm, (full, flag) => full.slice(0, full.length - flag.length) + span("flag", flag));
  }

  /**
   * JSON tokenizer.
   */
  function tokenizeJSON(code) {
    // Object keys: "key": → highlight key differently from string value
    return code
      .replace(/("(?:[^"\\]|\\.)*")(\s*:)/g, (_, key, colon) => span("key", key) + colon)
      .replace(/"(?:[^"\\]|\\.)*"/g, (m) => span("str", m))
      .replace(/\b(-?\d+\.?\d*(?:[eE][+-]?\d+)?)\b/g, (m) => span("num", m))
      .replace(/\b(true|false|null)\b/g, (m) => span("kw", m));
  }

  /**
   * YAML tokenizer.
   */
  function tokenizeYAML(code) {
    const COMMENTS = /(#[^\n]*)/g;
    const STRINGS = /("(?:[^"\\]|\\.)*"|'[^']*')/g;
    const KEYS = /^(\s*[-\s]*)([\w][\w\s-]*)(\s*:(?:\s|$))/gm;
    const NUMBERS = /(?<=:\s*)\b(\d+\.?\d*)\b/g;
    const BOOLS = /(?<=:\s*)\b(true|false|null|yes|no|on|off)\b/g;
    const ANCHORS = /(&\w+|\*\w+)/g;

    let out = "";
    let cursor = 0;
    const PROTECTED = new RegExp([STRINGS.source, COMMENTS.source].join("|"), "g");
    PROTECTED.lastIndex = 0;
    let match;
    while ((match = PROTECTED.exec(code)) !== null) {
      if (match.index > cursor) {
        out += tokenizeYAMLCode(code.slice(cursor, match.index), KEYS, NUMBERS, BOOLS, ANCHORS);
      }
      if (match[0].startsWith("#")) {
        out += span("cmt", match[0]);
      } else {
        out += span("str", match[0]);
      }
      cursor = match.index + match[0].length;
    }
    if (cursor < code.length) {
      out += tokenizeYAMLCode(code.slice(cursor), KEYS, NUMBERS, BOOLS, ANCHORS);
    }
    return out;
  }

  function tokenizeYAMLCode(code, KEYS, NUMBERS, BOOLS, ANCHORS) {
    return code
      .replace(KEYS, (_, indent, key, colon) => indent + span("key", key) + colon)
      .replace(NUMBERS, (m) => span("num", m))
      .replace(BOOLS, (m) => span("kw", m))
      .replace(ANCHORS, (m) => span("dec", m));
  }

  /**
   * HTTP request/response tokenizer.
   */
  function tokenizeHTTP(code) {
    return code
      // Request line: METHOD /path HTTP/1.1
      .replace(/^(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS|CONNECT|TRACE)\b/m, (m) => span("kw", m))
      // Response status line: HTTP/1.1 200 OK
      .replace(/^(HTTP\/\d\.?\d?\s+)(\d{3})([^\n]*)/m, (_, v, code_, text) =>
        v + span("num", code_) + span("cmt", text)
      )
      // Header names
      .replace(/^([A-Za-z][\w-]+)(\s*:)/gm, (_, h, c) => span("key", h) + c)
      // Header values (after the colon)
      .replace(/(?<=:\s)(.+)$/gm, (m) => span("str", m));
  }

  /**
   * JavaScript / TypeScript tokenizer.
   */
  function tokenizeJS(code) {
    const STRINGS = /(`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')/g;
    const COMMENTS = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g;
    const KEYWORDS = /\b(const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|class|extends|import|export|from|default|async|await|try|catch|finally|throw|new|typeof|instanceof|in|of|null|undefined|true|false|void|delete|yield|static|get|set|super|this)\b/g;
    const BUILTINS = /\b(console|Promise|Array|Object|String|Number|Boolean|Map|Set|Date|Error|JSON|Math|parseInt|parseFloat|isNaN|isFinite|setTimeout|clearTimeout|setInterval|clearInterval|fetch|document|window|navigator|location|localStorage|sessionStorage)\b/g;
    const NUMBERS = /\b(\d+\.?\d*(?:[eE][+-]?\d+)?n?)\b/g;

    let out = "";
    let cursor = 0;
    const PROTECTED = new RegExp([STRINGS.source, COMMENTS.source].join("|"), "g");
    PROTECTED.lastIndex = 0;
    let match;
    while ((match = PROTECTED.exec(code)) !== null) {
      if (match.index > cursor) {
        out += code.slice(cursor, match.index)
          .replace(KEYWORDS, (m) => span("kw", m))
          .replace(BUILTINS, (m) => span("bi", m))
          .replace(NUMBERS, (m) => span("num", m));
      }
      if (match[0].startsWith("/")) {
        out += span("cmt", match[0]);
      } else {
        out += span("str", match[0]);
      }
      cursor = match.index + match[0].length;
    }
    if (cursor < code.length) {
      out += code.slice(cursor)
        .replace(KEYWORDS, (m) => span("kw", m))
        .replace(BUILTINS, (m) => span("bi", m))
        .replace(NUMBERS, (m) => span("num", m));
    }
    return out;
  }
})();
