<template>
  <main class="min-h-screen bg-[#080d18] px-5 py-8 text-slate-200">
    <div class="mx-auto max-w-6xl">
      <div class="mb-5 flex items-center justify-between gap-3">
        <div>
          <p class="text-sm font-medium text-sky-300">GÜVENLİ CİHAZ OTURUMU</p>
          <h1 class="mt-2 text-2xl font-semibold text-white">{{ hostname || `Cihaz #${deviceId}` }}</h1>
          <p class="mt-1 text-sm text-slate-500">Salt-okunur komutlar · Komutlar sunucu tarafında allowlist ile doğrulanır</p>
        </div>
        <RouterLink class="btn" to="/">Envantere dön</RouterLink>
      </div>
      <section class="surface overflow-hidden rounded-2xl">
        <div class="flex items-center justify-between border-b border-slate-800 px-4 py-3">
          <div class="flex items-center gap-2 text-xs text-slate-400">
            <span class="h-2 w-2 rounded-full" :class="connected ? 'bg-emerald-400' : 'bg-amber-400'"></span>
            {{ connected ? "Bağlı" : "Bağlantı bekleniyor" }}
          </div>
          <button class="btn !px-3 !py-1.5 text-xs" :disabled="!connected" @click="closeConnection">Bağlantıyı kes</button>
        </div>
        <div ref="terminalHost" class="terminal h-[min(68vh,680px)] bg-[#070b13]"></div>
      </section>
      <p class="mt-4 text-xs leading-5 text-slate-500">
        Bu oturum yalnızca arayüz, VLAN, MAC tablosu ve sürüm gibi önceden tanımlı salt-okunur komutları kabul eder.
        Herhangi bir parola veya cihaz kimlik bilgisi tarayıcıya gönderilmez.
      </p>
    </div>
  </main>
</template>

<script setup lang="ts">
import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
import "@xterm/xterm/css/xterm.css";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { getToken } from "../api";

const route = useRoute();
const terminalHost = ref<HTMLElement | null>(null);
const connected = ref(false);
const hostname = ref("");
const deviceId = computed(() => String(route.params.deviceId));
let terminal: Terminal | null = null;
let fitAddon: FitAddon | null = null;
let socket: WebSocket | null = null;
let inputBuffer = "";

onMounted(() => {
  terminal = new Terminal({
    cursorBlink: true,
    convertEol: true,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    fontSize: 13,
    theme: { background: "#070b13", foreground: "#cbd5e1", cursor: "#38bdf8" },
  });
  fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  if (terminalHost.value) terminal.open(terminalHost.value);
  fitAddon.fit();
  terminal.writeln("OmniEyeNetwork read-only console");
  terminal.writeln("Kimlik doğrulama yapılıyor…");
  connect();
  window.addEventListener("resize", fitTerminal);
});

onBeforeUnmount(() => {
  window.removeEventListener("resize", fitTerminal);
  socket?.close();
  terminal?.dispose();
});

function connect() {
  const token = getToken();
  if (!token) {
    terminal?.writeln("\r\n\x1b[31mOturum bulunamadı. Yeniden giriş yapın.\x1b[0m");
    return;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  socket = new WebSocket(`${protocol}//${window.location.host}/api/v1/terminal/devices/${deviceId.value}`);
  socket.onopen = () => socket?.send(JSON.stringify({ token }));
  socket.onmessage = ({ data }) => {
    const message = JSON.parse(data);
    if (message.type === "ready") {
      connected.value = true;
      hostname.value = message.hostname;
      terminal?.writeln(`\r\nConnected to ${message.hostname}`);
      terminal?.writeln("Allowed commands:");
      for (const command of message.allowed_commands as string[]) terminal?.writeln(`  ${command}`);
      terminal?.writeln("\r\nType an allowed command and press Enter.\r\n");
      terminal?.write("$ ");
    } else if (message.type === "output") {
      terminal?.writeln("");
      terminal?.writeln(message.content);
      if (message.truncated) terminal?.writeln("[Output truncated]");
      terminal?.write("$ ");
    } else if (message.type === "error") {
      terminal?.writeln(`\r\n\x1b[33m${message.message}\x1b[0m`);
      terminal?.write("$ ");
    }
  };
  socket.onerror = () => terminal?.writeln("\r\n\x1b[31mWebSocket bağlantı hatası.\x1b[0m");
  socket.onclose = () => {
    connected.value = false;
    terminal?.writeln("\r\nOturum kapandı.");
  };

  terminal?.onData((data) => {
    if (!connected.value || !socket || socket.readyState !== WebSocket.OPEN) return;
    if (data === "\r") {
      terminal?.write("\r\n");
      if (inputBuffer.trim()) socket.send(JSON.stringify({ command: inputBuffer.trim() }));
      inputBuffer = "";
      return;
    }
    if (data === "\u007f") {
      if (inputBuffer.length) {
        inputBuffer = inputBuffer.slice(0, -1);
        terminal?.write("\b \b");
      }
      return;
    }
    if (data >= " " && data <= "~") {
      inputBuffer += data;
      terminal?.write(data);
    }
  });
}

function closeConnection() {
  if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: "close" }));
  socket?.close();
}

function fitTerminal() {
  fitAddon?.fit();
}
</script>
