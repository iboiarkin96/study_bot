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
      const lang = detectLanguage(block);
      if (!lang) { continue; }
      try {
        const raw = block.textContent || "";
        block.innerHTML = tokenize(escapeHTML(raw), lang);
        const pre = block.closest("pre");
        if (pre) {
          pre.setAttribute("data-lang", lang);
        }
      } catch (_) {
        // Fail silently — never break the page for a cosmetic feature.
      }
    }
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
