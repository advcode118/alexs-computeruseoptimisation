"use strict";

// Page DOM for a saved HTML fixture. Scripts and page.evaluate run here.
// fetch, XHR, and WebSocket throw. This process does not open a socket.

const readline = require("readline");
const vm = require("vm");

function offline() {
  throw new Error("offline replay does not open a network connection");
}

const consoleNoop = {
  log() {},
  error() {},
  warn() {},
  info() {},
  debug() {},
};

const context = vm.createContext({
  console: consoleNoop,
  fetch: offline,
  XMLHttpRequest: offline,
  WebSocket: offline,
});

const BLOCKS = new Set([
  "address",
  "article",
  "blockquote",
  "div",
  "form",
  "h1",
  "h2",
  "h3",
  "h4",
  "h5",
  "h6",
  "li",
  "main",
  "ol",
  "p",
  "section",
  "table",
  "tr",
  "ul",
]);

function textContent(node) {
  if (!node) return "";
  if (Object.prototype.hasOwnProperty.call(node, "text")) return String(node.text);
  let out = "";
  for (const child of node.children || []) out += textContent(child);
  return out;
}

function innerText(node) {
  if (!node) return "";
  if (Object.prototype.hasOwnProperty.call(node, "text")) return String(node.text);
  if (!node.tag || node.tag === "script" || node.tag === "style" || node.tag === "noscript") return "";
  let out = "";
  for (const child of node.children || []) {
    if (child.tag === "br") {
      out += "\n";
      continue;
    }
    const piece = innerText(child);
    if (!piece) continue;
    if (out && child.tag && BLOCKS.has(child.tag)) out += "\n" + piece;
    else out += piece;
  }
  return out;
}

function clean(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function collect(node, out) {
  for (const child of node.children || []) {
    if (child.tag) out.push(child);
    if (child.children) collect(child, out);
  }
}

class El {
  constructor(doc, tag) {
    this.ownerDocument = doc || this;
    this.tag = String(tag || "").toLowerCase();
    this.attrs = {};
    this.children = [];
    this.parent = null;
    this.listeners = {};
    this._value = "";
    this._checked = false;
  }

  get tagName() {
    return this.tag.toUpperCase();
  }

  get value() {
    return this._value;
  }

  set value(next) {
    this._value = String(next == null ? "" : next);
  }

  get textContent() {
    return textContent(this);
  }

  set textContent(next) {
    const text = { text: String(next == null ? "" : next), parent: this };
    this.children = [text];
  }

  get innerText() {
    return innerText(this);
  }

  get labels() {
    return labelsOf(this);
  }

  getAttribute(name) {
    const key = String(name || "").toLowerCase();
    if (!Object.prototype.hasOwnProperty.call(this.attrs, key)) return null;
    return this.attrs[key];
  }

  setAttribute(name, value) {
    this.attrs[String(name || "").toLowerCase()] = String(value == null ? "" : value);
  }

  addEventListener(type, fn) {
    const key = String(type || "");
    if (!this.listeners[key]) this.listeners[key] = [];
    this.listeners[key].push(fn);
  }

  querySelector(selector) {
    return queryAll(this, selector)[0] || null;
  }

  querySelectorAll(selector) {
    return queryAll(this, selector);
  }

  getElementById(id) {
    const want = String(id);
    const all = [];
    collect(this, all);
    return all.find((el) => el.getAttribute("id") === want) || null;
  }

  createElement(tag) {
    return new El(this.ownerDocument || this, tag);
  }

  appendChild(child) {
    if (child.parent && child.parent.children) {
      child.parent.children = child.parent.children.filter((item) => item !== child);
    }
    child.parent = this;
    if (!child.ownerDocument) child.ownerDocument = this.ownerDocument || this;
    this.children.push(child);
    return child;
  }
}

function createDocument(url) {
  const doc = new El(null, "#document");
  doc.ownerDocument = doc;
  doc.location = { href: url };
  Object.defineProperty(doc, "title", {
    get() {
      const node = this.querySelector("title");
      return node ? clean(textContent(node)) : "";
    },
  });
  Object.defineProperty(doc, "body", {
    get() {
      return this.querySelector("body");
    },
  });
  return doc;
}

function labelsOf(el) {
  const doc = el.ownerDocument;
  const found = [];
  const id = el.getAttribute("id");
  if (id && doc && doc.querySelectorAll) {
    for (const label of doc.querySelectorAll("label")) {
      if (label.getAttribute("for") === id) found.push(label);
    }
  }
  let parent = el.parent;
  while (parent) {
    if (parent.tag === "label") {
      found.push(parent);
      break;
    }
    parent = parent.parent;
  }
  return found;
}

function splitCommas(input) {
  const parts = [];
  let buf = "";
  let quote = "";
  let depth = 0;
  for (const ch of String(input || "")) {
    if (quote) {
      buf += ch;
      if (ch === quote) quote = "";
      continue;
    }
    if (ch === "'" || ch === '"') {
      quote = ch;
      buf += ch;
      continue;
    }
    if (ch === "(" || ch === "[") {
      depth += 1;
      buf += ch;
      continue;
    }
    if ((ch === ")" || ch === "]") && depth) {
      depth -= 1;
      buf += ch;
      continue;
    }
    if (ch === "," && depth === 0) {
      if (buf.trim()) parts.push(buf.trim());
      buf = "";
      continue;
    }
    buf += ch;
  }
  if (buf.trim()) parts.push(buf.trim());
  return parts;
}

function parseCompound(source) {
  const simples = [];
  let i = 0;
  const text = String(source || "").trim();
  while (i < text.length) {
    const ch = text[i];
    if (ch === "*") {
      simples.push({ kind: "any" });
      i += 1;
      continue;
    }
    if (ch === "#" || ch === ".") {
      let j = i + 1;
      while (j < text.length && /[A-Za-z0-9_-]/.test(text[j])) j += 1;
      simples.push({ kind: ch === "#" ? "id" : "class", value: text.slice(i + 1, j) });
      i = j;
      continue;
    }
    if (ch === "[") {
      const parsed = parseAttr(text, i);
      simples.push(parsed.simple);
      i = parsed.next;
      continue;
    }
    if (text.startsWith(":not(", i)) {
      let depth = 1;
      let j = i + 5;
      const start = j;
      while (j < text.length && depth) {
        if (text[j] === "(") depth += 1;
        else if (text[j] === ")") depth -= 1;
        if (depth) j += 1;
      }
      simples.push({ kind: "not", inner: parseCompound(text.slice(start, j)) });
      i = Math.min(text.length, j + 1);
      continue;
    }
    if (/[A-Za-z]/.test(ch)) {
      let j = i + 1;
      while (j < text.length && /[A-Za-z0-9-]/.test(text[j])) j += 1;
      simples.push({ kind: "tag", value: text.slice(i, j).toLowerCase() });
      i = j;
      continue;
    }
    throw new Error("bad selector " + text);
  }
  return simples;
}

function parseAttr(text, i) {
  let j = i + 1;
  while (j < text.length && /\s/.test(text[j])) j += 1;
  const nameStart = j;
  while (j < text.length && /[A-Za-z0-9_:-]/.test(text[j])) j += 1;
  const name = text.slice(nameStart, j).toLowerCase();
  if (!name) throw new Error("bad attribute selector");
  while (j < text.length && /\s/.test(text[j])) j += 1;
  if (text[j] === "]") return { simple: { kind: "attr", name, op: "exists", value: "" }, next: j + 1 };
  if (text[j] !== "=") throw new Error("bad attribute selector");
  j += 1;
  while (j < text.length && /\s/.test(text[j])) j += 1;
  let value = "";
  if (text[j] === '"' || text[j] === "'") {
    const quote = text[j];
    j += 1;
    const start = j;
    while (j < text.length && text[j] !== quote) j += 1;
    value = text.slice(start, j);
    j += 1;
  } else {
    const start = j;
    while (j < text.length && text[j] !== "]") j += 1;
    value = text.slice(start, j).trim();
  }
  while (j < text.length && text[j] !== "]") j += 1;
  if (text[j] !== "]") throw new Error("unterminated attribute");
  return { simple: { kind: "attr", name, op: "=", value }, next: j + 1 };
}

function matchSimple(el, simple) {
  if (!el || !el.tag) return false;
  if (simple.kind === "any") return true;
  if (simple.kind === "tag") return el.tag === simple.value;
  if (simple.kind === "id") return el.getAttribute("id") === simple.value;
  if (simple.kind === "class") return (el.getAttribute("class") || "").split(/\s+/).includes(simple.value);
  if (simple.kind === "attr") {
    const raw = el.getAttribute(simple.name);
    if (simple.op === "exists") return raw !== null;
    return raw === simple.value;
  }
  if (simple.kind === "not") return !simple.inner.every((part) => matchSimple(el, part));
  return false;
}

function matchesCompound(el, compound) {
  return compound.every((simple) => matchSimple(el, simple));
}

function matchesChain(el, compounds) {
  if (!compounds.length || !matchesCompound(el, compounds[compounds.length - 1])) return false;
  let index = compounds.length - 2;
  let parent = el.parent;
  while (parent && index >= 0) {
    if (parent.tag && matchesCompound(parent, compounds[index])) index -= 1;
    parent = parent.parent;
  }
  return index < 0;
}

function matchesSelector(el, selector) {
  return splitCommas(selector).some((part) => matchesChain(el, part.split(/\s+/).filter(Boolean).map(parseCompound)));
}

function queryAll(start, selector) {
  const all = [];
  collect(start, all);
  return all.filter((el) => matchesSelector(el, selector));
}

function accessibleName(el) {
  const aria = el.getAttribute("aria-label");
  if (aria) return clean(aria);
  const labelled = el.getAttribute("aria-labelledby");
  if (labelled) {
    const name = labelled
      .split(/\s+/)
      .map((id) => {
        const label = el.ownerDocument.getElementById(id);
        return label ? clean(label.innerText || label.textContent || "") : "";
      })
      .filter(Boolean)
      .join(" ");
    if (name) return name;
  }
  if (el.labels && el.labels.length) {
    const name = el.labels
      .map((label) => clean(label.innerText || label.textContent || ""))
      .filter(Boolean)
      .join(" ");
    if (name) return name;
  }
  return clean(el.innerText || el.textContent || el.getAttribute("placeholder") || el.getAttribute("title") || "");
}

function roleOf(el) {
  const explicit = el.getAttribute("role");
  if (explicit) return explicit.toLowerCase();
  if (el.tag === "a") return "link";
  if (el.tag === "button") return "button";
  if (el.tag === "textarea") return "textbox";
  if (el.tag === "select") return "combobox";
  if (el.tag === "input") {
    const type = (el.getAttribute("type") || "text").toLowerCase();
    if (type === "checkbox") return "checkbox";
    if (type === "radio") return "radio";
    if (type === "button" || type === "submit" || type === "reset") return "button";
    if (type === "search") return "searchbox";
    return "textbox";
  }
  return el.tag;
}

function nameMatches(el, name, exact) {
  const have = accessibleName(el);
  const want = clean(name);
  if (exact) return have === want;
  return have.toLowerCase().includes(want.toLowerCase());
}

function isAncestor(el, other) {
  let parent = other.parent;
  while (parent) {
    if (parent === el) return true;
    parent = parent.parent;
  }
  return false;
}

function find(doc, msg) {
  const all = [];
  collect(doc, all);
  const exact = msg.exact !== false;
  const name = msg.name || "";
  if (msg.by === "role") {
    return all.filter((el) => roleOf(el) === String(msg.role || "") && nameMatches(el, name, exact));
  }
  if (msg.by === "label") {
    const controls = [];
    for (const label of doc.querySelectorAll("label")) {
      const have = clean(label.innerText || label.textContent || "");
      const want = clean(name);
      const hit = exact ? have === want : have.toLowerCase().includes(want.toLowerCase());
      if (!hit) continue;
      const id = label.getAttribute("for");
      if (id) {
        const control = doc.getElementById(id);
        if (control) controls.push(control);
        continue;
      }
      const nested = label.querySelector("input, textarea, select, button");
      if (nested) controls.push(nested);
    }
    return controls.filter((el, index) => controls.indexOf(el) === index);
  }
  if (msg.by === "placeholder") {
    return all.filter((el) => {
      const placeholder = el.getAttribute("placeholder");
      if (placeholder == null) return false;
      const have = clean(placeholder);
      const want = clean(name);
      return exact ? have === want : have.toLowerCase().includes(want.toLowerCase());
    });
  }
  const hits = all.filter((el) => {
    const have = clean(el.innerText || "");
    if (!have) return false;
    const want = clean(name);
    return exact ? have === want : have.toLowerCase().includes(want.toLowerCase());
  });
  return hits.filter((el) => !hits.some((other) => other !== el && isAncestor(el, other)));
}

function dispatch(el, type) {
  const event = {
    type,
    target: el,
    defaultPrevented: false,
    preventDefault() {
      this.defaultPrevented = true;
    },
  };
  const chain = [];
  let node = el;
  while (node) {
    chain.push(node);
    node = node.parent;
  }
  for (const current of chain) {
    const list = (current.listeners && current.listeners[type]) || [];
    for (const fn of list) {
      fn.call(current, event);
      if (event.defaultPrevented) return event;
    }
  }
  return event;
}

function ancestor(el, tag) {
  let node = el.parent;
  while (node) {
    if (node.tag === tag) return node;
    node = node.parent;
  }
  return null;
}

function submitForm(form) {
  const event = dispatch(form, "submit");
  if (event.defaultPrevented) return {};
  const action = form.getAttribute("action");
  if (action) return { navigate: action };
  return {};
}

function actClick(el) {
  const event = dispatch(el, "click");
  if (event.defaultPrevented) return {};
  if (el.tag === "a") {
    const href = el.getAttribute("href");
    if (href && !href.toLowerCase().startsWith("javascript:")) return { navigate: href };
    return {};
  }
  const type = (el.getAttribute("type") || "").toLowerCase();
  const submitter =
    (el.tag === "button" && (type === "" || type === "submit")) || (el.tag === "input" && type === "submit");
  if (!submitter) return {};
  const form = ancestor(el, "form");
  if (!form) return {};
  return submitForm(form);
}

function actPress(el, key) {
  dispatch(el, "keydown");
  if (key === "Enter") {
    const form = ancestor(el, "form");
    if (form) return submitForm(form);
  }
  return {};
}

let state = { doc: null };

function buildNode(spec, doc, parent) {
  if (spec && Object.prototype.hasOwnProperty.call(spec, "text")) {
    parent.children.push({ text: String(spec.text), parent });
    return;
  }
  const el = new El(doc, spec.tag || "div");
  parent.appendChild(el);
  for (const [key, value] of Object.entries(spec.attrs || {})) el.setAttribute(key, value);
  if (el.tag === "input" || el.tag === "textarea") el.value = el.getAttribute("value") || "";
  for (const child of spec.children || []) buildNode(child, doc, el);
}

function loadTree(tree, url) {
  const doc = createDocument(url);
  for (const child of (tree && tree.children) || []) buildNode(child, doc, doc);
  state.doc = doc;
  context.document = doc;
  context.location = doc.location;
  context.window = { document: doc, location: doc.location };
  const errors = [];
  for (const script of doc.querySelectorAll("script")) {
    if (script.getAttribute("src")) {
      errors.push("refusing to load a script src");
      continue;
    }
    const code = script.textContent || "";
    if (!code.trim()) continue;
    try {
      vm.runInContext(code, context, { timeout: 1000 });
    } catch (err) {
      errors.push(String((err && err.message) || err));
    }
  }
  if (errors.length) throw new Error(errors.join("; "));
  return { url: doc.location.href, title: doc.title };
}

function evaluate(source) {
  if (!state.doc) throw new Error("no page is loaded");
  context.document = state.doc;
  context.location = state.doc.location;
  context.window = { document: state.doc, location: state.doc.location };
  const value = vm.runInContext("(" + source + ")()", context, { timeout: 1000 });
  return value === undefined ? null : value;
}

function handle(msg) {
  if (msg.op === "load") return loadTree(msg.tree, msg.url);
  if (!state.doc) throw new Error("no page is loaded");
  if (msg.op === "title") return state.doc.title;
  if (msg.op === "count") return find(state.doc, msg).length;
  if (msg.op === "act") {
    const found = find(state.doc, msg);
    if (found.length !== 1) throw new Error(found.length + " matches");
    if (msg.action === "click") return actClick(found[0]);
    if (msg.action === "fill") {
      found[0].value = msg.value || "";
      return {};
    }
    if (msg.action === "press") return actPress(found[0], msg.value || "");
    if (msg.action === "check") {
      found[0]._checked = true;
      return {};
    }
    if (msg.action === "uncheck") {
      found[0]._checked = false;
      return {};
    }
    throw new Error("bad action");
  }
  if (msg.op === "eval") return evaluate(msg.source);
  throw new Error("bad op");
}

function reply(payload) {
  process.stdout.write(JSON.stringify(payload) + "\n");
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity, terminal: false });
rl.on("line", (line) => {
  let msg = {};
  try {
    msg = JSON.parse(line);
    const value = handle(msg);
    reply({ id: msg.id, ok: true, value });
  } catch (err) {
    reply({ id: msg.id, ok: false, error: String((err && err.message) || err) });
  }
});
