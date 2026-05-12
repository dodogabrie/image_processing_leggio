// File: backend/scripts/language-tags.js
// Shared utility for detecting multi-language tags in CSV/XLSX column headers.
// No Node-specific imports: safe to import from both backend and Vite-bundled frontend.

const ISO_CODES = new Set([
  'it', 'en', 'fr', 'de', 'es', 'pt', 'ru', 'zh', 'ja', 'ar'
]);

// Italian language-name → ISO 639-1
const IT_NAME_TO_CODE = {
  italiano: 'it', inglese: 'en', francese: 'fr', tedesco: 'de',
  spagnolo: 'es', portoghese: 'pt', russo: 'ru', cinese: 'zh',
  giapponese: 'ja', arabo: 'ar'
};

// English language-name → ISO 639-1
const EN_NAME_TO_CODE = {
  italian: 'it', english: 'en', french: 'fr', german: 'de',
  spanish: 'es', portuguese: 'pt', russian: 'ru', chinese: 'zh',
  japanese: 'ja', arabic: 'ar'
};

/**
 * Detects a language tag in a single column header.
 * Recognizes:
 *   1. prefix[lang]                e.g. "title[en]"
 *   2. prefix_lang                 e.g. "title_en"   (only with whitelisted ISO codes)
 *   3. prefix (TRADUZIONE IN X)    e.g. "TITOLO PER LEGGIO\n(TRADUZIONE IN INGLESE)"
 *   4. prefix (X TRANSLATION)      e.g. "TITLE (ENGLISH TRANSLATION)"
 *
 * @param {string} header
 * @returns {{ prefix: string, language: string|null }}
 */
export function detectLanguageTag(header) {
  if (header == null) return { prefix: '', language: null };
  const raw = String(header);

  // 1. [lang] bracket form
  let m = raw.match(/^([\s\S]*?)\s*\[\s*([A-Za-z]{2,3})\s*\]\s*$/);
  if (m) return { prefix: m[1].trim(), language: m[2].toLowerCase() };

  // 2. _lang suffix form (only if suffix is a whitelisted ISO code → avoid false positives)
  m = raw.match(/^([\s\S]+)_([A-Za-z]{2,3})\s*$/);
  if (m && ISO_CODES.has(m[2].toLowerCase())) {
    return { prefix: m[1].trim(), language: m[2].toLowerCase() };
  }

  // 3. (TRADUZIONE IN <lingua>) parenthetical, Italian style
  m = raw.match(/^([\s\S]*?)[\s\n\r]*\(\s*traduzione\s+in\s+([a-zàèéìòù]+)\s*\)\s*$/i);
  if (m) {
    const code = IT_NAME_TO_CODE[m[2].toLowerCase()];
    if (code) return { prefix: m[1].trim(), language: code };
  }

  // 4. (<lang> TRANSLATION) parenthetical, English style
  m = raw.match(/^([\s\S]*?)[\s\n\r]*\(\s*([a-z]+)\s+translation\s*\)\s*$/i);
  if (m) {
    const code = EN_NAME_TO_CODE[m[2].toLowerCase()];
    if (code) return { prefix: m[1].trim(), language: code };
  }

  return { prefix: raw.trim(), language: null };
}

/**
 * Normalizes a string for prefix comparison: collapses whitespace, trims, lowercases.
 */
function normalize(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim().toLowerCase();
}

/**
 * Groups headers by their canonical base prefix and assigns a language to each.
 *
 * When a header has a tagged sibling sharing the same prefix (e.g. an untagged
 * Italian version next to "...(TRADUZIONE IN INGLESE)"), the untagged one is
 * promoted to language "it". Promotion only happens at a word boundary, so
 * "Titolone" is not grouped with "Titolo[en]".
 *
 * @param {string[]} headers
 * @returns {{
 *   basesByHeader: Map<string,string>,
 *   langByHeader: Map<string,string>,         // 'default' if no tag
 *   langsByBase: Object<string,string[]>,     // sorted, unique
 *   representative: string[]                  // one header per base, in first-seen order
 * }}
 */
export function groupHeadersByBase(headers) {
  const parsed = (headers || []).map(h => ({ header: h, ...detectLanguageTag(h) }));

  // Tagged bases sorted by length desc (longest match wins when promoting siblings)
  const taggedBases = [...new Set(
    parsed.filter(p => p.language && p.prefix).map(p => p.prefix)
  )].sort((a, b) => b.length - a.length);

  // Promote untagged headers whose prefix matches a tagged base at a word boundary
  for (const p of parsed) {
    if (p.language) continue;
    const normHeader = normalize(p.header);
    for (const base of taggedBases) {
      const normBase = normalize(base);
      if (!normBase) continue;
      if (!normHeader.startsWith(normBase)) continue;
      const tail = p.header.replace(/^\s+/, '').slice(base.length);
      // Boundary: end-of-string OR non-alphanumeric next char
      if (tail === '' || /^[\s\n\r(\[_\-]/.test(tail)) {
        p.prefix = base;
        p.language = 'it';
        break;
      }
    }
  }

  const basesByHeader = new Map();
  const langByHeader = new Map();
  const langSetsByBase = {};
  const seen = new Set();
  const representative = [];

  for (const p of parsed) {
    basesByHeader.set(p.header, p.prefix);
    langByHeader.set(p.header, p.language || 'default');
    langSetsByBase[p.prefix] = langSetsByBase[p.prefix] || new Set();
    langSetsByBase[p.prefix].add(p.language || 'default');
    if (!seen.has(p.prefix)) {
      seen.add(p.prefix);
      representative.push(p.header);
    }
  }

  const langsByBase = Object.fromEntries(
    Object.entries(langSetsByBase).map(([k, s]) => [k, [...s].sort()])
  );

  return { basesByHeader, langByHeader, langsByBase, representative };
}

/**
 * Returns true if the languages-by-base set for `base` contains any non-default tag.
 */
export function baseHasLanguageVariants(langsByBase, base) {
  const langs = langsByBase[base];
  if (!langs) return false;
  return langs.some(l => l !== 'default');
}
