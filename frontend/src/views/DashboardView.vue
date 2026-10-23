<template>
  <div class="min-h-screen bg-[#080d18]">
    <header class="border-b border-slate-800/80 bg-[#0b1220]/90">
      <div class="mx-auto flex max-w-[1440px] items-center justify-between px-5 py-4 lg:px-8">
        <div class="flex items-center gap-3">
          <div class="grid h-10 w-10 place-items-center rounded-xl bg-sky-500/15 font-bold text-sky-300">O</div>
          <div>
            <p class="font-semibold text-white">OmniEyeNetwork</p>
            <p class="text-xs text-slate-500">Network operations</p>
          </div>
        </div>
        <div class="flex items-center gap-3">
          <span class="rounded-full border border-slate-700 px-3 py-1 text-xs uppercase tracking-wide text-slate-300">
            {{ role || "user" }}
          </span>
          <button class="btn" @click="logout">Çıkış</button>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-[1440px] px-5 py-8 lg:px-8">
      <div class="mb-7 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p class="text-sm font-medium text-sky-300">ENVANTER / GENEL BAKIŞ</p>
          <h1 class="mt-2 text-3xl font-semibold tracking-tight text-white">Ağ durumu</h1>
          <p class="mt-2 text-sm text-slate-400">Kayıtlı cihazlar, bağlantı durumu ve port envanteri.</p>
        </div>
        <div class="flex gap-2">
          <button class="btn" :disabled="!selectedDevice || loading" @click="discoverPorts">
            Portları keşfet
          </button>
          <button v-if="role === 'admin'" class="btn btn-primary" @click="showCreate = true">
            Cihaz ekle
          </button>
        </div>
      </div>

      <p v-if="error" class="mb-5 rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
        {{ error }}
      </p>
      <p v-if="notice" class="mb-5 rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-300">
        {{ notice }}
      </p>

      <section class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <article v-for="card in summaryCards" :key="card.label" class="surface rounded-2xl p-5">
          <p class="text-sm text-slate-400">{{ card.label }}</p>
          <p class="mt-3 text-3xl font-semibold text-white">{{ card.value }}</p>
          <p class="mt-2 text-xs text-slate-500">{{ card.caption }}</p>
        </article>
      </section>

      <section class="mt-7">
        <div class="surface overflow-hidden rounded-2xl">
          <div class="flex flex-wrap items-center justify-between gap-3 p-5">
            <div>
              <h2 class="font-semibold text-white">Cihaz envanteri</h2>
              <p class="mt-1 text-xs text-slate-500">{{ devices.length }} cihaz</p>
            </div>
            <select v-model="groupFilter" class="field max-w-56" aria-label="Cihaz grubuna göre filtrele">
              <option value="">Tüm gruplar</option>
              <option v-for="group in groups" :key="group.id" :value="String(group.id)">{{ group.name }}</option>
            </select>
          </div>
          <div class="overflow-x-auto">
            <table class="w-full min-w-[760px] text-left text-sm">
              <thead class="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th class="px-5 py-3 font-medium">Cihaz</th>
                  <th class="px-4 py-3 font-medium">Üretici / model</th>
                  <th class="px-4 py-3 font-medium">Durum</th>
                  <th class="px-4 py-3 font-medium">Yedek</th>
                  <th class="px-5 py-3 text-right font-medium">İşlemler</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="device in filteredDevices" :key="device.id" class="table-row">
                  <td class="px-5 py-4">
                    <button class="font-medium text-slate-100 hover:text-sky-300" @click="selectDevice(device)">
                      {{ device.hostname }}
                    </button>
                    <p class="mt-1 font-mono text-xs text-slate-500">{{ device.ip_address }}</p>
                  </td>
                  <td class="px-4 py-4 text-slate-300">
                    <span>{{ device.vendor }}</span>
                    <p class="mt-1 text-xs text-slate-500">{{ device.model || device.os_type }}</p>
                  </td>
                  <td class="px-4 py-4">
                    <span class="inline-flex items-center gap-2 text-xs" :class="statusColor(device.status)">
                      <span class="h-1.5 w-1.5 rounded-full bg-current"></span>{{ device.status }}
                    </span>
                  </td>
                  <td class="px-4 py-4 text-xs text-slate-400">{{ formatDate(device.last_backup_at) }}</td>
                  <td class="px-5 py-4">
                    <div class="flex justify-end gap-2">
                      <button class="btn !px-2.5 !py-1.5 text-xs" @click="selectDevice(device)">Portlar</button>
                      <button
                        v-if="canOperate"
                        class="btn !px-2.5 !py-1.5 text-xs"
                        @click="openTerminal(device)"
                      >Terminal</button>
                      <button
                        v-if="canOperate"
                        class="btn !px-2.5 !py-1.5 text-xs"
                        @click="loadLiveConfig(device)"
                      >Canlı config</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!filteredDevices.length">
                  <td colspan="5" class="px-5 py-12 text-center text-sm text-slate-500">
                    {{ loading ? "Envanter yükleniyor…" : "Bu filtrede cihaz bulunamadı." }}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

      </section>

      <section class="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,0.65fr)]">
        <div class="surface min-w-0 rounded-2xl">
          <div class="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800/80 p-5">
            <div>
              <h2 class="font-semibold text-white">{{ selectedDevice?.hostname || "Switch port görünümü" }}</h2>
              <p class="mt-1 text-xs text-slate-500">
                {{ selectedDevice ? `${selectedDevice.ip_address} · ${ports.length} port` : "Cihaz seçerek portları görüntüleyin" }}
                <span v-if="lastDiscoveryAt"> · Son keşif {{ formatDate(lastDiscoveryAt) }}</span>
                <span v-else-if="selectedDevice"> · Henüz keşif zamanı yok</span>
              </p>
            </div>
            <div v-if="selectedDevice" class="flex flex-wrap items-center gap-2">
              <button
                class="btn !py-2 text-xs"
                :disabled="portsLoading"
                @click="loadPorts(selectedDevice.id)"
              >{{ portsLoading ? "Yükleniyor…" : "Envanteri yenile" }}</button>
              <input
                v-model.trim="portSearch"
                class="field !w-44 !py-2 text-xs"
                placeholder="Port ara"
                aria-label="Port ara"
              />
              <div class="flex rounded-lg border border-slate-700 p-1" aria-label="Port görünümü">
                <button
                  class="rounded-md px-3 py-1.5 text-xs"
                  :class="portView === 'grid' ? 'bg-sky-500/20 text-sky-200' : 'text-slate-400 hover:text-white'"
                  :aria-pressed="portView === 'grid'"
                  @click="portView = 'grid'"
                >Ön panel</button>
                <button
                  class="rounded-md px-3 py-1.5 text-xs"
                  :class="portView === 'list' ? 'bg-sky-500/20 text-sky-200' : 'text-slate-400 hover:text-white'"
                  :aria-pressed="portView === 'list'"
                  @click="portView = 'list'"
                >Liste</button>
              </div>
            </div>
          </div>

          <div class="flex flex-wrap gap-x-5 gap-y-2 px-5 py-3 text-xs text-slate-400" aria-label="Port durumu açıklaması">
            <span class="inline-flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-emerald-400"></i>Up</span>
            <span class="inline-flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-slate-500"></i>Down</span>
            <span class="inline-flex items-center gap-2"><i class="h-2.5 w-2.5 rounded-sm bg-amber-400"></i>Diğer / bilinmiyor</span>
            <span class="text-slate-500">Renkler son keşfedilen durumu gösterir; hover/odak ayrıntıyı yükler, cihaza bağlanmaz.</span>
          </div>

          <div v-if="portsLoading" class="px-5 py-12 text-center text-sm text-slate-400" role="status">
            Port envanteri yükleniyor…
          </div>
          <div v-else-if="selectedDevice && !ports.length" class="px-5 py-12 text-center">
            <p class="text-sm text-slate-300">Bu cihaz için henüz port kaydı yok.</p>
            <p class="mt-2 text-xs text-slate-500">Arka plan port keşfini başlatıp daha sonra listeyi yenileyin.</p>
          </div>
          <div v-else-if="selectedDevice && !filteredPorts.length" class="px-5 py-12 text-center text-sm text-slate-500">
            Aramanızla eşleşen port yok.
          </div>

          <div
            v-else-if="selectedDevice && portView === 'grid'"
            class="grid gap-3 p-5"
            :style="{ gridTemplateColumns: 'repeat(auto-fill, minmax(6.25rem, 1fr))' }"
          >
            <button
              v-for="port in filteredPorts"
              :key="port.id"
              class="group relative min-h-24 rounded-xl border p-3 text-left transition hover:-translate-y-0.5 hover:border-sky-400/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
              :class="portTileClass(port)"
              :aria-label="portAccessibleName(port)"
              :aria-pressed="selectedPort?.id === port.id"
              @mouseenter="hoveredPortId = port.id"
              @mouseleave="hoveredPortId = null"
              @focus="hoveredPortId = port.id"
              @blur="hoveredPortId = null"
              @click="selectPort(port)"
            >
              <span class="block truncate font-mono text-xs font-semibold text-slate-100">{{ port.name }}</span>
              <span class="mt-3 flex items-center justify-between gap-2">
                <span class="inline-flex items-center gap-1.5 text-[11px] capitalize" :class="statusColor(port.status)">
                  <i class="h-1.5 w-1.5 rounded-full bg-current"></i>{{ port.status }}
                </span>
                <span class="text-[10px] text-slate-400">{{ port.vlan ? `V${port.vlan}` : "—" }}</span>
              </span>
              <span
                v-if="hoveredPortId === port.id"
                class="pointer-events-none absolute left-1/2 top-[calc(100%+0.35rem)] z-20 hidden w-56 -translate-x-1/2 rounded-lg border border-slate-600 bg-slate-950 p-3 text-left text-xs shadow-xl group-hover:block group-focus:block"
                role="tooltip"
              >
                <strong class="block truncate text-slate-100">{{ port.name }}</strong>
                <span class="mt-2 block text-slate-300">Durum: {{ port.status }} · Admin: {{ port.admin_status }}</span>
                <span class="mt-1 block text-slate-400">VLAN: {{ port.vlan ?? "Atanmamış" }} · Hız: {{ port.speed || "Bilinmiyor" }}</span>
                <span class="mt-1 block truncate text-slate-400">MAC: {{ port.mac_address || "Bilinmiyor" }}</span>
                <span class="mt-1 block truncate text-slate-500">{{ port.description || "Açıklama yok" }}</span>
                <span class="mt-2 block text-slate-500">Keşif: {{ formatDate(port.last_discovered_at) }}</span>
              </span>
            </button>
          </div>

          <div v-else-if="selectedDevice" class="overflow-x-auto">
            <table class="w-full min-w-[620px] text-left text-sm">
              <thead class="bg-slate-900/70 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th class="px-5 py-3 font-medium">Port</th>
                  <th class="px-4 py-3 font-medium">Durum</th>
                  <th class="px-4 py-3 font-medium">VLAN</th>
                  <th class="px-4 py-3 font-medium">MAC</th>
                  <th class="px-5 py-3 text-right font-medium">Keşif</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="port in filteredPorts" :key="port.id" class="table-row">
                  <td class="px-5 py-3">
                    <button
                      class="font-mono text-xs text-slate-200 hover:text-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400"
                      :aria-pressed="selectedPort?.id === port.id"
                      @focus="hoveredPortId = port.id"
                      @blur="hoveredPortId = null"
                      @click="selectPort(port)"
                    >{{ port.name }}</button>
                    <p v-if="hoveredPortId === port.id" class="mt-1 text-xs text-slate-500">
                      {{ port.description || "Açıklama yok" }} · Admin: {{ port.admin_status }} · {{ port.speed || "Hız bilinmiyor" }}
                    </p>
                  </td>
                  <td class="px-4 py-3" :class="statusColor(port.status)">{{ port.status }}</td>
                  <td class="px-4 py-3 text-slate-300">{{ port.vlan ?? "—" }}</td>
                  <td class="px-4 py-3 font-mono text-xs text-slate-400">{{ port.mac_address || "—" }}</td>
                  <td class="px-5 py-3 text-right text-xs text-slate-500">{{ formatDate(port.last_discovered_at) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <aside class="surface min-w-0 rounded-2xl p-5" aria-live="polite">
          <template v-if="selectedPort">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <p class="text-xs font-medium uppercase tracking-wide text-sky-300">PORT DETAYI</p>
                <h3 class="mt-2 break-all font-mono text-lg font-semibold text-white">{{ selectedPort.name }}</h3>
              </div>
              <span class="shrink-0 rounded-full px-2.5 py-1 text-xs capitalize" :class="portBadgeClass(selectedPort.status)">
                {{ selectedPort.status }}
              </span>
            </div>
            <dl class="mt-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
              <dt class="text-slate-500">Admin durumu</dt><dd class="text-right text-slate-200">{{ selectedPort.admin_status }}</dd>
              <dt class="text-slate-500">VLAN</dt><dd class="text-right text-slate-200">{{ selectedPort.vlan ?? "Atanmamış" }}</dd>
              <dt class="text-slate-500">MAC adresi</dt><dd class="break-all text-right font-mono text-xs text-slate-200">{{ selectedPort.mac_address || "Bilinmiyor" }}</dd>
              <dt class="text-slate-500">Hız / duplex</dt><dd class="text-right text-slate-200">{{ selectedPort.speed || "Bilinmiyor" }} / {{ selectedPort.duplex || "Bilinmiyor" }}</dd>
              <dt class="text-slate-500">Açıklama</dt><dd class="text-right text-slate-200">{{ selectedPort.description || "Açıklama yok" }}</dd>
              <dt class="text-slate-500">Son keşif</dt><dd class="text-right text-slate-200">{{ formatDate(selectedPort.last_discovered_at) }}</dd>
              <dt class="text-slate-500">Durum değişimi</dt><dd class="text-right text-slate-200">{{ formatDate(selectedPort.last_change) }}</dd>
            </dl>
            <div class="mt-6 border-t border-slate-800 pt-5">
              <button
                v-if="canOperate && selectedDevice"
                class="btn btn-primary w-full"
                :disabled="portConfigLoading"
                @click="loadLivePortConfig"
              >{{ portConfigLoading ? "Cihazdan alınıyor…" : "Canlı interface config'i getir" }}</button>
              <p v-else class="text-xs text-slate-500">Canlı interface config yalnızca admin/operator rollerine açıktır.</p>
              <p v-if="portConfigError" class="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-200" role="alert">
                {{ portConfigError }}
              </p>
              <div v-if="portConfigText" class="mt-4">
                <p class="mb-2 text-xs text-slate-400">Cihazdan alındı · {{ formatDate(portConfigRetrievedAt) }}</p>
                <pre class="max-h-80 overflow-auto rounded-lg border border-slate-700 bg-slate-950 p-3 text-xs leading-5 text-slate-300">{{ portConfigText }}</pre>
              </div>
            </div>
          </template>
          <div v-else class="grid min-h-52 place-items-center text-center">
            <div>
              <p class="text-sm font-medium text-slate-300">Bir port seçin</p>
              <p class="mt-2 max-w-xs text-xs leading-5 text-slate-500">Port özellikleri burada görünür. Canlı config yalnızca açıkça istendiğinde yüklenir.</p>
            </div>
          </div>
        </aside>
      </section>
    </main>

    <div v-if="showCreate" class="fixed inset-0 z-20 grid place-items-center bg-black/70 p-4" @click.self="showCreate = false">
      <form class="surface w-full max-w-xl space-y-4 rounded-2xl p-6" @submit.prevent="createDevice">
        <div class="flex items-start justify-between">
          <div>
            <h2 class="text-lg font-semibold text-white">Envantere cihaz ekle</h2>
            <p class="mt-1 text-xs text-slate-500">Kimlik bilgileri Vault kullanılarak şifrelenir.</p>
          </div>
          <button class="text-slate-400 hover:text-white" type="button" aria-label="Kapat" @click="showCreate = false">✕</button>
        </div>
        <div class="grid gap-3 sm:grid-cols-2">
          <input v-model.trim="newDevice.hostname" class="field" placeholder="Hostname" required />
          <input v-model.trim="newDevice.ip_address" class="field" placeholder="Yönetim IP adresi" required />
          <input v-model.trim="newDevice.vendor" class="field" placeholder="Üretici (örn. Cisco)" required />
          <input v-model.trim="newDevice.model" class="field" placeholder="Model" />
          <input v-model.trim="newDevice.os_type" class="field" placeholder="Netmiko OS türü" required />
          <select v-model="newDevice.group_id" class="field">
            <option :value="null">Grup yok</option>
            <option v-for="group in groups" :key="group.id" :value="group.id">{{ group.name }}</option>
          </select>
          <input v-model.trim="newDevice.username" class="field" placeholder="SSH kullanıcı adı" autocomplete="off" />
          <input v-model="newDevice.password" class="field" placeholder="SSH parolası" type="password" autocomplete="new-password" />
        </div>
        <p v-if="formError" class="text-sm text-rose-300">{{ formError }}</p>
        <div class="flex justify-end gap-2">
          <button class="btn" type="button" @click="showCreate = false">İptal</button>
          <button class="btn btn-primary" type="submit" :disabled="saving">{{ saving ? "Kaydediliyor…" : "Cihazı ekle" }}</button>
        </div>
      </form>
    </div>

    <div v-if="configDevice" class="fixed inset-0 z-30 grid place-items-center bg-black/75 p-4" @click.self="configDevice = null">
      <section class="surface flex max-h-[85vh] w-full max-w-5xl flex-col rounded-2xl">
        <div class="flex items-start justify-between border-b border-slate-800 p-5">
          <div>
            <h2 class="font-semibold text-white">Canlı konfigürasyon · {{ configDevice.hostname }}</h2>
            <p class="mt-1 text-xs text-slate-500">Cihazdan anlık alınmıştır; hassas içerik içerebilir.</p>
          </div>
          <button class="text-slate-400 hover:text-white" aria-label="Kapat" @click="configDevice = null">✕</button>
        </div>
        <pre class="overflow-auto p-5 text-xs leading-5 text-slate-300">{{ liveConfig }}</pre>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import axios from "axios";
import { useRouter } from "vue-router";
import { api, clearSession, Device, DeviceGroup, getRole, LivePortConfig, Port } from "../api";

const router = useRouter();
const role = ref(getRole());
const canOperate = computed(() => role.value === "admin" || role.value === "operator");
const devices = ref<Device[]>([]);
const groups = ref<DeviceGroup[]>([]);
const ports = ref<Port[]>([]);
const selectedDevice = ref<Device | null>(null);
const selectedPort = ref<Port | null>(null);
const portView = ref<"grid" | "list">("grid");
const portSearch = ref("");
const hoveredPortId = ref<number | null>(null);
const groupFilter = ref("");
const loading = ref(false);
const portsLoading = ref(false);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const formError = ref("");
const showCreate = ref(false);
const configDevice = ref<Device | null>(null);
const liveConfig = ref("");
const portConfigLoading = ref(false);
const portConfigText = ref("");
const portConfigError = ref("");
const portConfigRetrievedAt = ref<string | null>(null);
const newDevice = reactive({
  hostname: "",
  ip_address: "",
  vendor: "",
  model: "",
  os_type: "cisco_ios",
  group_id: null as number | null,
  username: "",
  password: "",
});
let portLoadSequence = 0;
let portConfigRequestSequence = 0;

const filteredDevices = computed(() => groupFilter.value
  ? devices.value.filter((device) => String(device.group_id) === groupFilter.value)
  : devices.value);
const filteredPorts = computed(() => {
  const search = portSearch.value.toLocaleLowerCase("tr-TR");
  return ports.value.filter((port) => (
    !search
    || port.name.toLocaleLowerCase("tr-TR").includes(search)
    || (port.description || "").toLocaleLowerCase("tr-TR").includes(search)
    || String(port.vlan ?? "").includes(search)
    || (port.mac_address || "").toLocaleLowerCase("tr-TR").includes(search)
  ));
});
const lastDiscoveryAt = computed(() => ports.value
  .map((port) => port.last_discovered_at)
  .filter((value): value is string => Boolean(value))
  .sort((left, right) => Date.parse(right) - Date.parse(left))[0] || null);
const summaryCards = computed(() => [
  { label: "Toplam cihaz", value: devices.value.length, caption: `${groups.value.length} envanter grubu` },
  { label: "Çevrimiçi", value: devices.value.filter((device) => device.status === "online").length, caption: "Son erişim durumuna göre" },
  { label: "Aktif port", value: ports.value.filter((port) => port.status === "up").length, caption: "Seçili cihazda keşfedilen" },
  { label: "Yedek durumu", value: devices.value.filter((device) => device.last_backup_at).length, caption: "En az bir config yedeği" },
]);

onMounted(loadInventory);

async function loadInventory() {
  loading.value = true;
  error.value = "";
  try {
    const [deviceResponse, groupResponse] = await Promise.all([
      api.get<Device[]>("/devices"),
      api.get<DeviceGroup[]>("/groups"),
    ]);
    devices.value = deviceResponse.data;
    groups.value = groupResponse.data;
    if (!selectedDevice.value && devices.value.length) await selectDevice(devices.value[0]);
    else if (selectedDevice.value) await loadPorts(selectedDevice.value.id);
  } catch {
    error.value = "Envanter yüklenemedi. API ve kullanıcı yetkilerini kontrol edin.";
  } finally {
    loading.value = false;
  }
}

async function selectDevice(device: Device) {
  portConfigRequestSequence += 1;
  portConfigLoading.value = false;
  selectedDevice.value = device;
  selectedPort.value = null;
  portSearch.value = "";
  portConfigText.value = "";
  portConfigError.value = "";
  portConfigRetrievedAt.value = null;
  await loadPorts(device.id);
}

async function loadPorts(deviceId: number) {
  const requestSequence = ++portLoadSequence;
  portsLoading.value = true;
  ports.value = [];
  error.value = "";
  try {
    const allPorts: Port[] = [];
    let skip = 0;
    while (true) {
      const { data } = await api.get<Port[]>("/ports", {
        params: { device_id: deviceId, skip, limit: 500 },
      });
      if (requestSequence !== portLoadSequence) return;
      allPorts.push(...data);
      if (data.length < 500) break;
      skip += data.length;
    }
    ports.value = allPorts.sort((left, right) =>
      left.name.localeCompare(right.name, undefined, { numeric: true, sensitivity: "base" }),
    );
    if (selectedPort.value) {
      selectedPort.value = ports.value.find((port) => port.id === selectedPort.value?.id) || null;
      if (!selectedPort.value) {
        portConfigText.value = "";
        portConfigError.value = "";
        portConfigRetrievedAt.value = null;
      }
    }
  } catch {
    if (requestSequence === portLoadSequence) {
      error.value = "Port bilgileri yüklenemedi.";
    }
  } finally {
    if (requestSequence === portLoadSequence) {
      portsLoading.value = false;
    }
  }
}

function selectPort(port: Port) {
  portConfigRequestSequence += 1;
  portConfigLoading.value = false;
  selectedPort.value = port;
  portConfigText.value = "";
  portConfigError.value = "";
  portConfigRetrievedAt.value = null;
}

async function createDevice() {
  saving.value = true;
  formError.value = "";
  try {
    const payload = { ...newDevice };
    await api.post("/devices", payload);
    Object.assign(newDevice, {
      hostname: "", ip_address: "", vendor: "", model: "",
      os_type: "cisco_ios", group_id: null, username: "", password: "",
    });
    showCreate.value = false;
    notice.value = "Cihaz envantere eklendi.";
    await loadInventory();
  } catch (requestError: unknown) {
    formError.value = axios.isAxiosError(requestError) && typeof requestError.response?.data?.detail === "string"
      ? requestError.response.data.detail
      : "Cihaz kaydedilemedi.";
  } finally {
    saving.value = false;
  }
}

async function discoverPorts() {
  if (!selectedDevice.value) return;
  notice.value = "";
  try {
    await api.post("/ports/discovery/run", null, { params: { device_id: selectedDevice.value.id } });
    notice.value = `Port keşfi ${selectedDevice.value.hostname} için kuyruğa alındı. Birkaç dakika sonra listeyi yenileyin.`;
  } catch {
    error.value = "Port keşfi başlatılamadı. Celery kuyruğunu kontrol edin.";
  }
}

async function loadLiveConfig(device: Device) {
  configDevice.value = device;
  liveConfig.value = "Cihazdan konfigürasyon alınıyor…";
  try {
    const { data } = await api.get(`/devices/${device.id}/live-config`);
    liveConfig.value = data.config_text;
  } catch {
    liveConfig.value = "Canlı konfigürasyon alınamadı.";
  }
}

async function loadLivePortConfig() {
  if (!selectedDevice.value || !selectedPort.value) return;
  const requestSequence = ++portConfigRequestSequence;
  const deviceId = selectedDevice.value.id;
  const portId = selectedPort.value.id;
  portConfigLoading.value = true;
  portConfigText.value = "";
  portConfigError.value = "";
  portConfigRetrievedAt.value = null;
  try {
    const { data } = await api.get<LivePortConfig>(
      `/devices/${deviceId}/ports/${portId}/live-config`,
    );
    if (
      requestSequence !== portConfigRequestSequence
      || selectedDevice.value?.id !== deviceId
      || selectedPort.value?.id !== portId
    ) return;
    portConfigText.value = data.config_text;
    portConfigRetrievedAt.value = data.retrieved_at;
  } catch (requestError: unknown) {
    if (requestSequence !== portConfigRequestSequence) return;
    portConfigError.value = axios.isAxiosError(requestError)
      && typeof requestError.response?.data?.detail === "string"
      ? requestError.response.data.detail
      : "Interface config alınamadı. Cihaz erişimini ve yetkileri kontrol edin.";
  } finally {
    if (requestSequence === portConfigRequestSequence) {
      portConfigLoading.value = false;
    }
  }
}

function openTerminal(device: Device) {
  router.push({ name: "terminal", params: { deviceId: device.id } });
}

function logout() {
  clearSession();
  router.replace({ name: "login" });
}

function statusColor(status: string) {
  if (status === "online" || status === "up") return "text-emerald-400";
  if (status === "error") return "text-rose-400";
  if (status === "unknown") return "text-amber-400";
  return "text-slate-400";
}

function portTileClass(port: Port) {
  const selection = selectedPort.value?.id === port.id
    ? "ring-2 ring-sky-400 border-sky-400/70"
    : "border-slate-700/80";
  const state = port.status === "up"
    ? "bg-emerald-500/10 hover:bg-emerald-500/15"
    : port.status === "down"
      ? "bg-slate-800/80 hover:bg-slate-700/80"
      : "bg-amber-500/10 hover:bg-amber-500/15";
  return `${selection} ${state}`;
}

function portBadgeClass(status: string) {
  if (status === "up") return "bg-emerald-500/15 text-emerald-300";
  if (status === "down") return "bg-slate-700 text-slate-300";
  return "bg-amber-500/15 text-amber-200";
}

function portAccessibleName(port: Port) {
  return `${port.name}, ${port.status}, admin ${port.admin_status}, VLAN ${port.vlan ?? "atanmamış"}, MAC ${port.mac_address || "bilinmiyor"}. Ayrıntıları aç.`;
}

function formatDate(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString("tr-TR") : "Henüz yok";
}
</script>
