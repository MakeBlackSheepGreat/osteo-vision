<template>
  <section>
    <h2>Review State</h2>
    <button @click="emit('change', 'accepted')">Accept</button>
    <button @click="emit('change', 'modified')">Modify</button>
    <button @click="emit('change', 'rejected')">Reject</button>
  </section>
</template>

<script setup lang="ts">
const emit = defineEmits<{
  (event: "change", value: "accepted" | "modified" | "rejected"): void;
}>();
</script>
