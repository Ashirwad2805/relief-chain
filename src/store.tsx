/**
 * store.tsx — Live Store Re-export Bridge
 *
 * All pages import `useStore` from here.
 * This bridge connects all pages directly to the FastAPI live store.
 */
export * from '@/api/liveStore';
export { useStore, LiveStoreProvider } from '@/api/liveStore';
