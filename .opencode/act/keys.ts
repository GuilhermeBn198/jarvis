// Parser unico de teclas em sintaxe NATURAL (case-insensitive), consumido
// tanto pelo caminho foreground (ps.ts, keybd_event) quanto pelo background
// (win.ts, PostMessage WM_KEYDOWN/UP).
//
// Sintaxe: acordes separados por espaco ou virgula; nomes conhecidos
// (enter, esc, tab, f1..f24, ...), letras/digitos e `plus`; combos com
// ctrl+/alt+/shift+/win+ (ex.: ctrl+shift+esc). NAO e arquivo de plugin.

export type ModName = "ctrl" | "shift" | "alt" | "win";

export type KeyChord = {
  mods: ModName[]; // ordem canonica: ctrl, shift, alt, win
  vk: number;
  extended: boolean;
  onlyDown: boolean; // BG (PostMessage): char so KEYDOWN evita insercao dupla; FG (keybd_event) manda down+up
  name: string;
};

export const MOD_VK: Record<ModName, number> = { ctrl: 0x11, shift: 0x10, alt: 0x12, win: 0x5b };

const NAMED: Record<string, { vk: number; extended?: boolean }> = {
  enter: { vk: 0x0d },
  return: { vk: 0x0d },
  esc: { vk: 0x1b },
  escape: { vk: 0x1b },
  tab: { vk: 0x09 },
  backspace: { vk: 0x08 },
  delete: { vk: 0x2e, extended: true },
  del: { vk: 0x2e, extended: true },
  space: { vk: 0x20 },
  up: { vk: 0x26, extended: true },
  down: { vk: 0x28, extended: true },
  left: { vk: 0x25, extended: true },
  right: { vk: 0x27, extended: true },
  home: { vk: 0x24, extended: true },
  end: { vk: 0x23, extended: true },
  pgup: { vk: 0x21, extended: true },
  pageup: { vk: 0x21, extended: true },
  pgdn: { vk: 0x22, extended: true },
  pagedown: { vk: 0x22, extended: true },
  insert: { vk: 0x2d, extended: true },
  ins: { vk: 0x2d, extended: true },
  plus: { vk: 0xbb }, // VK_OEM_PLUS
  caps: { vk: 0x14 },
  capslock: { vk: 0x14 },
};

const MODS: Record<string, ModName> = {
  ctrl: "ctrl",
  control: "ctrl",
  shift: "shift",
  alt: "alt",
  win: "win",
  super: "win",
  meta: "win",
};

const MOD_ORDER: ModName[] = ["ctrl", "shift", "alt", "win"];

const EXAMPLES = 'exemplos: "enter", "ctrl+c", "ctrl+shift+esc", "alt+f4", "win+r"';

function resolveKeyName(name: string): { vk: number; extended: boolean } | null {
  if (/^f([1-9]|1[0-9]|2[0-4])$/.test(name)) {
    return { vk: 0x70 + (Number(name.slice(1)) - 1), extended: false };
  }
  if (/^[a-z]$/.test(name)) return { vk: name.toUpperCase().charCodeAt(0), extended: false };
  if (/^[0-9]$/.test(name)) return { vk: 0x30 + Number(name), extended: false };
  const n = NAMED[name];
  return n ? { vk: n.vk, extended: n.extended === true } : null;
}

function isCharKey(vk: number): boolean {
  return (
    (vk >= 0x30 && vk <= 0x39) || // digitos
    (vk >= 0x41 && vk <= 0x5a) || // letras
    vk === 0x20 || // space
    vk === 0xbb // plus (VK_OEM_PLUS)
  );
}

function parseChord(token: string): KeyChord {
  const parts = token.split("+").map((p) => p.trim().toLowerCase());
  if (parts.some((p) => p === "")) {
    throw new Error(`tecla invalida "${token}": operador '+' sem tecla. Use um modificador seguido de uma tecla — ${EXAMPLES}`);
  }
  const mods = new Set<ModName>();
  let key: { vk: number; extended: boolean } | null = null;
  let keyName = "";
  for (const part of parts) {
    const mod = MODS[part];
    if (mod) {
      mods.add(mod);
      continue;
    }
    const k = resolveKeyName(part);
    if (!k) {
      throw new Error(`tecla desconhecida "${part}" em "${token}" — ${EXAMPLES}`);
    }
    key = k;
    keyName = part;
  }
  if (!key) {
    throw new Error(`"${token}" e so modificador: falta a tecla. Use ctrl+c, alt+f4, win+r — ${EXAMPLES}`);
  }
  return {
    mods: MOD_ORDER.filter((m) => mods.has(m)),
    vk: key.vk,
    extended: key.extended,
    onlyDown: isCharKey(key.vk),
    name: keyName,
  };
}

// Converte a string de keys em acordes validados. Falha cedo (antes de
// qualquer script) com mensagem didatica para token desconhecido/vazio.
export function parseKeys(keys: string): KeyChord[] {
  const raw = String(keys ?? "").trim();
  if (!raw) {
    throw new Error(`informe as teclas a enviar — ${EXAMPLES}`);
  }
  return raw
    .split(/[\s,]+/)
    .filter((t) => t.length > 0)
    .map(parseChord);
}

function hex2(vk: number): string {
  return `0x${vk.toString(16).toUpperCase().padStart(2, "0")}`;
}

// Foreground: keybd_event (mesmo padrao P/Invoke do act_click). Mods down ->
// tecla (down+up) -> mods up em ordem reversa. Em FG down+up e digitacao
// normal; a insercao dupla medida em RichEdit foi no caminho BG (PostMessage),
// entao `onlyDown` e mitigacao SO do background. NUNCA chama
// SetForegroundWindow: o envio vai para a janela em foco (a sintaxe natural
// substitui o SendKeys, que interpretava `ctrl+v` como "ctrl" + Shift(v)).
export function buildForegroundKeyScript(keys: string): string {
  const chords = parseKeys(keys);
  const body = chords
    .map((c) => {
      const lines = c.mods.map((m) => `keybd_event(${hex2(MOD_VK[m])}, 0, 0, 0)`);
      lines.push(`keybd_event(${hex2(c.vk)}, 0, 0, 0)`);
      lines.push(`Start-Sleep -Milliseconds 20`);
      lines.push(`keybd_event(${hex2(c.vk)}, 0, 2, 0)`);
      for (const m of [...c.mods].reverse()) lines.push(`keybd_event(${hex2(MOD_VK[m])}, 0, 2, 0)`);
      return lines.join("; ");
    })
    .join("; Start-Sleep -Milliseconds 30; ");
  return `Add-Type -Namespace W -Name K -MemberDefinition '[DllImport("user32.dll")] public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);'; ${body}`;
}

// Payload do background: acordes validados serializados para o script.
export function encodeKeyChords(chords: KeyChord[]): string {
  return JSON.stringify(chords.map((c) => ({ mods: c.mods, vk: c.vk, ex: c.extended, onlyDown: c.onlyDown })));
}
