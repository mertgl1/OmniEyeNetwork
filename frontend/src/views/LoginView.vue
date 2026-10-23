<template>
  <main class="flex min-h-screen items-center justify-center bg-[#080d18] px-5">
    <section class="surface w-full max-w-md rounded-2xl p-8">
      <div class="mb-8 flex items-center gap-3">
        <div class="grid h-12 w-12 place-items-center rounded-xl bg-sky-500/15 text-sky-300">
          <span class="text-xl font-bold">O</span>
        </div>
        <div>
          <p class="text-lg font-semibold text-white">OmniEyeNetwork</p>
          <p class="text-sm text-slate-400">Network operations console</p>
        </div>
      </div>
      <h1 class="text-2xl font-semibold text-white">Güvenli oturum açın</h1>
      <p class="mt-2 text-sm text-slate-400">Kurumsal hesabınızla devam edin.</p>
      <form class="mt-7 space-y-4" @submit.prevent="submit">
        <label class="block space-y-2 text-sm text-slate-300">
          Kullanıcı adı
          <input v-model.trim="username" class="field" autocomplete="username" required />
        </label>
        <label class="block space-y-2 text-sm text-slate-300">
          Parola
          <input v-model="password" class="field" type="password" autocomplete="current-password" required />
        </label>
        <p v-if="error" class="rounded-lg border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">
          {{ error }}
        </p>
        <button class="btn btn-primary w-full" type="submit" :disabled="loading">
          {{ loading ? "Doğrulanıyor…" : "Oturum aç" }}
        </button>
      </form>
      <p class="mt-6 text-xs leading-5 text-slate-500">
        Erişim, Active Directory gruplarınız ve OmniEyeNetwork rolünüzle sınırlandırılır.
      </p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";
import { api, setSession } from "../api";

const router = useRouter();
const username = ref("");
const password = ref("");
const loading = ref(false);
const error = ref("");

async function submit() {
  loading.value = true;
  error.value = "";
  try {
    const { data } = await api.post("/auth/login", {
      username: username.value,
      password: password.value,
    });
    setSession(data.access_token, data.role);
    await router.replace({ name: "dashboard" });
  } catch {
    error.value = "Giriş başarısız. Bilgilerinizi ve AD bağlantısını kontrol edin.";
  } finally {
    loading.value = false;
  }
}
</script>
