// Synthetic assessment fixture. No network, database or provider access.
export async function reserve(store, slot, participant) {
  if (await store.find(slot)) return { confirmed: false, reason: 'occupied' };
  await store.insert({ slot, participant });
  return { confirmed: true };
}
