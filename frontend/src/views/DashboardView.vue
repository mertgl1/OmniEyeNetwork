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

      <section class="mt-7 grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(340px,0.8fr)]">
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

        <div class="surface overflow-hidden rounded-2xl">
          <div class="flex items-center justify-between border-b border-slate-800/80 p-5">
            <div>
              <h2 class="font-semibold text-white">{{ selectedDevice?.hostname || "Port görünümü" }}</h2>
              <p class="mt-1 text-xs text-slate-500">
                {{ selectedDevice ? `${selectedDevice.ip_address} · ${ports.length} port` : "Cihaz seçerek portları görüntüleyin" }}
              </p>
            </div>
            <span v-if="selectedDevice" class="rounded-lg bg-slate-800 px-2.5 py-1 text-xs text-slate-300">
              {{ ports.filter((port) => port.status === "up").length }} up
            </span>
          </div>
          <div class="max-h-[480px] overflow-y-auto">
            <div v-for="port in ports" :key="port.id" class="table-row flex items-center justify-between gap-3 px-5 py-3">
              <div class="min-w-0">
                <p class="truncate text-sm font-medium text-slate-200">{{ port.name }}</p>
                <p class="mt-1 truncate text-xs text-slate-500">{{ port.description || port.mac_address || "—" }}</p>
              </div>
              <div class="shrink-0 text-right">
                <span class="text-xs" :class="statusColor(port.status)">{{ port.status }}</span>
                <p class="mt-1 text-xs text-slate-500">{{ port.vlan ? `VLAN ${port.vlan}` : "No VLAN" }}</p>
              </div>
            </div>
            <p v-if="selectedDevice && !ports.length" class="px-5 py-10 text-center text-sm text-slate-500">
              Henüz port kaydı yok. “Portları keşfet” ile arka plan senkronizasyonu başlatın.
            </p>
          </div>
        </div>
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
import { api, clearSession, Device, DeviceGroup, getRole, Port } from "../api";

const router = useRouter();
const role = ref(getRole());
const canOperate = computed(() => role.value === "admin" || role.value === "operator");
const devices = ref<Device[]>([]);
const groups = ref<DeviceGroup[]>([]);
const ports = ref<Port[]>([]);
const selectedDevice = ref<Device | null>(null);
const groupFilter = ref("");
const loading = ref(false);
const saving = ref(false);
const error = ref("");
const notice = ref("");
const formError = ref("");
const showCreate = ref(false);
const configDevice = ref<Device | null>(null);
const liveConfig = ref("");
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

const filteredDevices = computed(() => groupFilter.value
  ? devices.value.filter((device) => String(device.group_id) === groupFilter.value)
  : devices.value);
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
  selectedDevice.value = device;
  await loadPorts(device.id);
}

async function loadPorts(deviceId: number) {
  try {
    const { data } = await api.get<Port[]>("/ports", { params: { device_id: deviceId, limit: 500 } });
    ports.value = data;
  } catch {
    error.value = "Port bilgileri yüklenemedi.";
  }
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
  return "text-slate-400";
}

function formatDate(value: string | null) {
  return value ? new Date(value).toLocaleString("tr-TR") : "Henüz yok";
}
</script>
