// bas install ke liye, caching zaroori nahi
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('fetch', () => {});
